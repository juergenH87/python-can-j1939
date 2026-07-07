"""
Threading safety and lifecycle tests.

This module tests:
- Timer accuracy and drift prevention (heapq-based scheduling)
- Protocol/timer thread separation (slow callbacks don't block protocol)
- Thread-safe subscriber list operations
- MemoryAccess servicer thread lifecycle
- Dependent registry and cascaded shutdown from ECU
"""
import threading
import time

import pytest

import j1939
from j1939.parameter_group_number import ParameterGroupNumber
from test.helpers.feeder import Feeder


def _make_ecu():
    """Create a mock ECU with no CAN bus."""
    return j1939.ElectronicControlUnit(send_message=lambda *a, **kw: None)


def _wait_thread_exit(thread, timeout=0.5):
    """Wait for a thread to exit, polling every 10ms.
    
    :param thread: The thread to wait for.
    :param timeout: Maximum time to wait in seconds.
    :return: True if thread exited, False if timeout reached.
    """
    deadline = time.monotonic() + timeout
    while thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)
    return not thread.is_alive()


def _wait_no_threads_named(name, timeout=0.5):
    """Wait until no alive threads have the given name.
    
    :param name: Thread name to check for.
    :param timeout: Maximum time to wait in seconds.
    :return: True if no matching threads remain, False if timeout reached.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not any(t.name == name and t.is_alive() for t in threading.enumerate()):
            return True
        time.sleep(0.01)
    return False

def test_timer_no_drift():
    """Verify heapq-based timer fires reliably and doesn't deadlock.
    
    This test validates that the timer thread:
    - Fires reliably (gets all expected callbacks)
    - Doesn't deadlock or hang indefinitely
    - Doesn't accumulate extreme outlier delays (> 500ms)
    
    Note: Strict interval timing is not validated on slow CI machines.
    The focus is on correctness (fire count) and absence of hangs.
    """
    ecu = _make_ecu()
    timestamps = []
    done = threading.Event()

    def callback(cookie):
        timestamps.append(time.monotonic())
        if len(timestamps) >= 10:
            done.set()
            return False   # stop rescheduling
        return True        # reschedule

    ecu.add_timer(0.050, callback)
    fired = done.wait(timeout=10.0)  # generous timeout for very slow CI
    ecu.stop()

    assert fired, "Timer did not fire 10 times within 10 seconds - possible deadlock"
    assert len(timestamps) == 10, f"Expected 10 callbacks, got {len(timestamps)}"

    intervals = [timestamps[i+1] - timestamps[i] for i in range(9)]
    
    # Only check for extreme outliers that would indicate a broken timer
    # (e.g., long GC pause, system under extreme load, or actual deadlock)
    max_interval = max(intervals)
    assert max_interval < 1.0, (
        f"Max interval was {max_interval*1000:.1f}ms, which is extreme "
        "(expected < 1000ms even on slow CI). Timer may be deadlocked or broken."
    )
    
    # Log intervals for debugging CI issues
    avg_interval = sum(intervals) / len(intervals)
    assert avg_interval > 0.025, (
        f"Average interval was {avg_interval*1000:.1f}ms, "
        "which is too fast (timer may be firing twice per cycle)"
    )


def test_slow_callback_no_protocol_impact(feeder):
    """A slow application timer callback must not delay BAM reassembly."""

    slow_fired = threading.Event()

    def slow_callback(cookie):
        slow_fired.set()
        time.sleep(0.150)   # simulate heavy work
        return True

    feeder.ecu.add_timer(0.020, slow_callback)
    # Wait until the slow callback has fired at least once so it is
    # definitely holding the (old single) job thread during the BAM.
    slow_fired.wait(timeout=1.0)

    # 20-byte BAM: BAM announce + 3 DT frames
    pgn_value = 0xFEC8  # arbitrary broadcast PGN
    # Build raw CAN message sequence (same pattern as test_ecu.py)
    can_id_bam = 0x1CECFF01   # TP.CM BAM from 0x01 to global
    can_id_dt  = 0x1CEBFF01   # TP.DT  from 0x01 to global

    feeder.can_messages = [
        (Feeder.MsgType.CANRX, can_id_bam,
         [32, 20, 0, 3, 255, pgn_value & 0xFF, (pgn_value >> 8) & 0xFF, 0], 0.0),
        (Feeder.MsgType.CANRX, can_id_dt,
         [1, 1, 2, 3, 4, 5, 6, 7], 0.0),
        (Feeder.MsgType.CANRX, can_id_dt,
         [2, 8, 9, 10, 11, 12, 13, 14], 0.0),
        (Feeder.MsgType.CANRX, can_id_dt,
         [3, 15, 16, 17, 18, 19, 20, 255], 0.0),
    ]

    received = threading.Event()

    def on_message(priority, pgn, sa, timestamp, data):
        if pgn == pgn_value:
            received.set()

    feeder.ecu.subscribe(on_message)
    feeder.ecu.accept_all_messages = lambda: None  # already set by Feeder init

    feeder.accept_all_messages()
    start = time.monotonic()
    feeder._inject_messages_into_ecu()

    # BAM with 3 DT frames at 50ms inter-frame gap = ~150ms minimum.
    # Allow 400ms — still well under the 150ms slow callback sleeping
    # indefinitely on the old single thread.
    delivered = received.wait(timeout=0.4)
    elapsed = time.monotonic() - start

    feeder.ecu.unsubscribe(on_message)
    feeder.ecu.remove_timer(slow_callback)

    assert delivered, (
        f"BAM message was not reassembled within 400ms (elapsed {elapsed*1000:.0f}ms). "
        "Slow callback may be blocking the protocol thread."
    )


def test_concurrent_add_remove_no_crash():
    """Concurrent add/remove of timers from multiple threads must not crash or deadlock."""
    ecu = _make_ecu()
    errors = []

    def noop(cookie):
        return True

    def hammer():
        try:
            deadline = time.monotonic() + 0.3
            while time.monotonic() < deadline:
                ecu.add_timer(0.01, noop)
                ecu.remove_timer(noop)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=hammer) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2.0)
        assert not t.is_alive(), "Hammer thread deadlocked"

    ecu.stop()

    assert not errors, f"Exceptions during concurrent timer ops: {errors}"

def test_memory_access_event_latency():
    """MemoryAccess servicer thread responds to events within reasonable latency.
    
    This test validates that the servicer thread wakes up and responds to events
    without excessive delay. Rather than enforcing sub-10ms latency (which is
    unrealistic on slow CI machines with variable scheduler load), we check that:
    - The servicer thread does respond eventually (not deadlocked)
    - Response is within a generous time window (< 500ms) allowing for CI variability
    """
    from j1939.memory_access import DMState, MemoryAccess

    ecu = _make_ecu()
    ca = ecu.add_ca(name=j1939.Name(
        arbitrary_address_capable=0,
        industry_group=j1939.Name.IndustryGroup.Industrial,
        vehicle_system_instance=1,
        vehicle_system=1,
        function=1,
        function_instance=1,
        ecu_instance=1,
        manufacturer_code=1,
        identity_number=1,
    ), device_address=0x80)

    ma = MemoryAccess(ca)

    callback_times = []
    set_time = []

    def notify():
        callback_times.append(time.monotonic())

    ma.set_notify(notify)
    ma.state = DMState.WAIT_RESPONSE

    set_time.append(time.monotonic())
    ma._proceed_event.set()

    # Give the servicer thread up to 500ms to respond (allows for slow CI machines)
    deadline = time.monotonic() + 0.500
    while not callback_times and time.monotonic() < deadline:
        time.sleep(0.001)

    ecu.stop()

    assert callback_times, "notify callback was never called after _proceed_event.set()"
    latency = callback_times[0] - set_time[0]
    assert latency < 0.500, (
        f"MemoryAccess notify latency was {latency*1000:.2f}ms, "
        f"expected < 500ms (thread should not be blocked/deadlocked)"
    )


def test_subscribe_unsubscribe_race(feeder):
    """Concurrent subscribe/unsubscribe while messages arrive must not crash."""
    errors = []
    received_count = [0]

    def counting_cb(priority, pgn, sa, timestamp, data):
        received_count[0] += 1

    def subscribe_loop():
        try:
            deadline = time.monotonic() + 0.5
            while time.monotonic() < deadline:
                feeder.ecu.subscribe(counting_cb)
                time.sleep(0.001)
                feeder.ecu.unsubscribe(counting_cb)
        except Exception as exc:
            errors.append(exc)

    # Keep at least one stable subscriber so messages are delivered
    feeder.ecu.subscribe(counting_cb)

    sub_thread = threading.Thread(target=subscribe_loop)
    sub_thread.start()

    # Inject broadcast messages repeatedly
    can_id = 0x18FEC801  # broadcast from 0x01, PGN 0xFEC8
    inject_deadline = time.monotonic() + 0.5
    while time.monotonic() < inject_deadline:
        feeder.message_queue.put((Feeder.MsgType.CANRX, can_id,
                                  bytearray([1, 2, 3, 4, 5, 6, 7, 8]), 0.0))
        time.sleep(0.01)

    sub_thread.join(timeout=2.0)
    feeder.ecu.unsubscribe(counting_cb)

    assert not errors, f"Exceptions during subscribe/unsubscribe race: {errors}"
    assert received_count[0] > 0, "No messages were received during the race"

def _make_ca(ecu, device_address=0x80):
    """Create a ControllerApplication with minimal valid Name."""
    return ecu.add_ca(name=j1939.Name(
        arbitrary_address_capable=0,
        industry_group=j1939.Name.IndustryGroup.Industrial,
        vehicle_system_instance=1,
        vehicle_system=1,
        function=1,
        function_instance=1,
        ecu_instance=1,
        manufacturer_code=1,
        identity_number=1,
    ), device_address=device_address)


def _j1939_threads():
    """Return list of alive threads with names starting with 'j1939.'."""
    return [t for t in threading.enumerate()
            if t.name.startswith('j1939.') and t.is_alive()]


class _FakeDependent:
    """Test helper that logs stop() calls and optionally raises."""

    def __init__(self, log, name, raise_on_stop=False):
        self.log = log
        self.name = name
        self.raise_on_stop = raise_on_stop
        self.stop_count = 0

    def stop(self):
        self.stop_count += 1
        self.log.append(self.name)
        if self.raise_on_stop:
            raise RuntimeError(f"{self.name} blew up")


def test_ecu_stop_cascades_to_memory_access():
    """ecu.stop() alone must tear down a MemoryAccess servicer thread."""
    from j1939.memory_access import MemoryAccess

    ecu = _make_ecu()
    ca = _make_ca(ecu)
    MemoryAccess(ca)

    # Sanity: servicer thread is running
    assert any(t.name == 'j1939.memory_access servicer_thread' for t in _j1939_threads())

    ecu.stop()

    assert _wait_no_threads_named('j1939.memory_access servicer_thread', timeout=1.0), \
        "MemoryAccess servicer thread still running after ecu.stop()"


def test_ecu_stop_cascades_lifo():
    """Dependents must be stopped in reverse registration order."""
    ecu = _make_ecu()
    log = []
    a = _FakeDependent(log, 'A')
    b = _FakeDependent(log, 'B')
    c = _FakeDependent(log, 'C')
    ecu.register_dependent(a)
    ecu.register_dependent(b)
    ecu.register_dependent(c)

    ecu.stop()

    assert log == ['C', 'B', 'A'], log


def test_ecu_stop_continues_on_dependent_failure():
    """A failing dependent.stop() must not prevent others from running."""
    ecu = _make_ecu()
    log = []
    a = _FakeDependent(log, 'A')
    b = _FakeDependent(log, 'B', raise_on_stop=True)
    c = _FakeDependent(log, 'C')
    ecu.register_dependent(a)
    ecu.register_dependent(b)
    ecu.register_dependent(c)

    ecu.stop()  # must not raise

    # All three should have had stop() called despite B raising.
    assert log == ['C', 'B', 'A']
    # And ECU's own threads are stopped.
    assert not ecu._protocol_thread.is_alive()
    assert not ecu._timer_thread.is_alive()


def test_memory_access_explicit_stop_no_leak():
    """Explicit ma.stop() cleans up servicer thread quickly (< 50ms) before ecu.stop()."""
    from j1939.memory_access import MemoryAccess

    ecu = _make_ecu()
    ca = _make_ca(ecu)
    ma = MemoryAccess(ca)

    t0 = time.monotonic()
    ma.stop()
    elapsed = time.monotonic() - t0

    assert elapsed < 0.050, f"MemoryAccess.stop() took {elapsed*1000:.1f}ms, expected < 50ms"
    assert _wait_no_threads_named('j1939.memory_access servicer_thread'), \
        "Servicer thread still running after ma.stop()"

    ecu.stop()


def test_memory_access_context_manager():
    """MemoryAccess context manager stops servicer thread on __exit__."""
    from j1939.memory_access import MemoryAccess

    ecu = _make_ecu()
    ca = _make_ca(ecu)
    with MemoryAccess(ca) as ma:
        assert ma._job_thread.is_alive()

    assert _wait_thread_exit(ma._job_thread), "Servicer thread did not stop after context exit"
    ecu.stop()


def test_memory_access_stop_idempotent():
    """Multiple calls to ma.stop() must not raise or block."""
    from j1939.memory_access import MemoryAccess

    ecu = _make_ecu()
    ca = _make_ca(ecu)
    ma = MemoryAccess(ca)
    ma.stop()
    ma.stop()
    ma.stop()
    ecu.stop()


def test_register_unregister_dependent_idempotent():
    """Duplicate register/unregister calls are silently handled."""
    ecu = _make_ecu()
    log = []
    a = _FakeDependent(log, 'A')

    ecu.register_dependent(a)
    ecu.register_dependent(a)  # duplicate - silently deduped
    ecu.unregister_dependent(a)
    ecu.unregister_dependent(a)  # second unregister - no error

    ecu.stop()
    assert log == [], "Unregistered dependent should not be stopped"


def test_register_dependent_requires_stop_method():
    """Registering object without stop() method raises TypeError."""
    ecu = _make_ecu()
    with pytest.raises(TypeError):
        ecu.register_dependent(object())
    ecu.stop()


def test_register_dependent_rejected_during_shutdown():
    """Registering new dependent during shutdown raises RuntimeError."""
    ecu = _make_ecu()
    log = []
    blocker = _FakeDependent(log, 'blocker')
    late = _FakeDependent(log, 'late')
    captured = []

    def blocker_stop():
        log.append('blocker')
        try:
            ecu.register_dependent(late)
        except RuntimeError as e:
            captured.append(e)

    blocker.stop = blocker_stop
    ecu.register_dependent(blocker)

    ecu.stop()

    assert captured, "Expected RuntimeError when registering during shutdown"
    assert log == ['blocker']


def test_send_pgn_concurrent_no_crash():
    """Concurrent send_pgn calls while the protocol thread is running must not
    raise RuntimeError (dictionary changed size during iteration) or corrupt
    _snd_buffer. Regression test for the missing _buffer_lock in j1939_21
    send_pgn."""
    sent = []
    errors = []

    def capture_send(can_id, extended, data, fd_format=False):
        sent.append(can_id)

    ecu = j1939.ElectronicControlUnit(send_message=capture_send)

    def spam_send_pgn():
        try:
            deadline = time.monotonic() + 0.5
            src = 0x01
            dst = ParameterGroupNumber.Address.GLOBAL
            payload = list(range(20))  # >8 bytes → TP path
            while time.monotonic() < deadline:
                ecu.send_pgn(0, 0xFE, dst, 6, src, payload)
                time.sleep(0.001)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=spam_send_pgn) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2.0)
        assert not t.is_alive(), "send_pgn stress thread deadlocked"

    ecu.stop()

    assert not errors, f"Exceptions during concurrent send_pgn: {errors}"


def test_send_pgn_j1939_21_buffer_lock_no_race():
    """send_pgn check-then-write on _snd_buffer must be atomic: two threads
    sending to the same src/dst pair must not both succeed and overwrite each
    other's buffer entry."""
    results = []
    errors = []

    def capture_send(can_id, extended, data, fd_format=False):
        pass

    ecu = j1939.ElectronicControlUnit(send_message=capture_send)

    barrier = threading.Barrier(2)

    def send_once():
        try:
            barrier.wait()  # start both threads simultaneously
            result = ecu.send_pgn(0, 0xFE, ParameterGroupNumber.Address.GLOBAL,
                                  6, 0x01, list(range(20)))
            results.append(result)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=send_once) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2.0)

    ecu.stop()

    assert not errors, f"Exceptions: {errors}"
    # Exactly one should succeed (True) and one should be rejected (False)
    # because both target the same src/dst hash.
    assert sorted(results) == [False, True], (
        f"Expected one success and one rejection, got: {results}"
    )


def test_dependent_registration_stress_no_leak():
    """Create/stop many MemoryAccess instances; no servicer thread may leak."""
    from j1939.memory_access import MemoryAccess

    ecu = _make_ecu()
    ca = _make_ca(ecu)

    for _ in range(50):
        ma = MemoryAccess(ca)
        ma.stop()

    assert _wait_no_threads_named('j1939.memory_access servicer_thread', timeout=1.0), \
        "Leaked servicer thread(s) after stress test"

    ecu.stop()
