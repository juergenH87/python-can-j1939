"""ISO 11783-3 ETP: timing, aborts, validation and TP/ETP selection.

These tests drive one ECU directly: what it sends is captured, and the peer's
frames are fed in with ``notify``, so a test can wait between frames. The
loopback tests connect two ECUs to each other and run whole transfers.
"""
import queue
import threading
import time

import pytest

import j1939
from j1939.iso11783_etp import ISO11783_ETP

LOCAL = 0x80
PEER = 0x90
PGN = 0xDF00
OTHER_PGN = 0xDE00

R = ISO11783_ETP.AbortReason


def _u24(value):
    return [value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF]


def _u32(value):
    return [value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF, (value >> 24) & 0xFF]


def cm_id(src, dst):
    return (7 << 26) | (0xC8 << 16) | (dst << 8) | src


def dt_id(src, dst):
    return (7 << 26) | (0xC7 << 16) | (dst << 8) | src


def rts(size, pgn=PGN):
    return [20] + _u32(size) + _u24(pgn)


def cts(count, next_packet, pgn=PGN):
    return [21, count] + _u24(next_packet) + _u24(pgn)


def dpo(count, offset, pgn=PGN):
    return [22, count] + _u24(offset) + _u24(pgn)


def eom(size, pgn=PGN):
    return [23] + _u32(size) + _u24(pgn)


def abort(reason, pgn=PGN):
    return [255, reason, 0xFF, 0xFF, 0xFF] + _u24(pgn)


def payload_of(size):
    return [(i * 7 + 3) & 0xFF for i in range(size)]


class Station:
    """One ECU whose sent frames are captured, accepting messages to LOCAL."""

    def __init__(self, **ecu_kwargs):
        self.frames = queue.Queue()
        self.received = queue.Queue()
        self.ecu = j1939.ElectronicControlUnit(send_message=self._send, **ecu_kwargs)
        self.ecu.subscribe(self._on_message, device_address=LOCAL)

    def _send(self, can_id, extended_id, data, fd_format=False):
        self.frames.put((can_id, list(data)))

    def _on_message(self, priority, pgn, sa, timestamp, data):
        self.received.put((pgn, sa, list(data)))

    def feed(self, can_id, data):
        self.ecu.notify(can_id, data, time.time())

    def expect(self, can_id, data, timeout=2.0):
        got = self.frames.get(timeout=timeout)
        assert got == (can_id, list(data)), f"sent {got[0]:08x} {got[1]}, expected {can_id:08x} {list(data)}"

    def quiet(self, within):
        try:
            got = self.frames.get(timeout=within)
        except queue.Empty:
            return
        raise AssertionError(f"unexpected frame {got[0]:08x} {got[1]}")

    def skip(self, count, timeout=2.0):
        return [self.frames.get(timeout=timeout) for _ in range(count)]

    @property
    def etp(self):
        return self.ecu.j1939_dll.etp

    def stop(self):
        self.ecu.stop()


@pytest.fixture()
def station():
    s = Station()
    yield s
    s.stop()


def start_send(station, size, data=None):
    data = payload_of(size) if data is None else data
    assert station.ecu.send_pgn(0, PGN >> 8, PEER, 6, LOCAL, data)
    station.expect(cm_id(LOCAL, PEER), rts(size))
    return data


def start_receive(station, size, burst):
    station.feed(cm_id(PEER, LOCAL), rts(size))
    station.expect(cm_id(LOCAL, PEER), cts(burst, 1))


# --- sending -----------------------------------------------------------------

def test_send_hold_waits_t4(station):
    """After a hold the originator waits T4, not Th, before giving up."""
    start_send(station, 2000)
    station.feed(cm_id(PEER, LOCAL), cts(0, 1))
    station.quiet(0.7)
    station.feed(cm_id(PEER, LOCAL), cts(1, 1))
    station.expect(cm_id(LOCAL, PEER), dpo(1, 0))


def test_send_hold_times_out_after_t4(station):
    start_send(station, 2000)
    station.feed(cm_id(PEER, LOCAL), cts(0, 1))
    station.quiet(0.9)
    station.expect(cm_id(LOCAL, PEER), abort(R.TIMEOUT), timeout=0.5)
    assert not station.etp.has_send_session(LOCAL, PEER)


def test_send_times_out_without_cts(station):
    start_send(station, 2000)
    station.quiet(1.1)
    station.expect(cm_id(LOCAL, PEER), abort(R.TIMEOUT), timeout=0.5)


def test_send_bytes_payload(station):
    """A bytes payload is sent like a list of byte values."""
    data = bytes(payload_of(1800))
    start_send(station, 1800, data)
    station.feed(cm_id(PEER, LOCAL), cts(2, 1))
    station.expect(cm_id(LOCAL, PEER), dpo(2, 0))
    station.expect(dt_id(LOCAL, PEER), [1] + list(data[0:7]))
    station.expect(dt_id(LOCAL, PEER), [2] + list(data[7:14]))


def test_send_abort_from_receiver_ends_send(station):
    start_send(station, 2000)
    station.feed(cm_id(PEER, LOCAL), abort(R.RESOURCES))
    station.quiet(0.2)
    assert not station.etp.has_send_session(LOCAL, PEER)


def test_send_abort_for_other_pgn_is_ignored(station):
    start_send(station, 2000)
    station.feed(cm_id(PEER, LOCAL), abort(R.RESOURCES, OTHER_PGN))
    station.feed(cm_id(PEER, LOCAL), cts(1, 1))
    station.expect(cm_id(LOCAL, PEER), dpo(1, 0))


def test_send_cts_wrong_pgn_aborts_and_ends(station):
    start_send(station, 2000)
    station.feed(cm_id(PEER, LOCAL), cts(1, 1, OTHER_PGN))
    station.expect(cm_id(LOCAL, PEER), abort(R.UNEXPECTED_CTS_PGN, OTHER_PGN))
    assert not station.etp.has_send_session(LOCAL, PEER)
    station.quiet(1.4)


def test_send_cts_out_of_range_aborts(station):
    start_send(station, 2000)
    station.feed(cm_id(PEER, LOCAL), cts(1, 287))
    station.expect(cm_id(LOCAL, PEER), abort(R.CTS_REQUESTED_PACKETS_EXCEEDS_SIZE))
    assert not station.etp.has_send_session(LOCAL, PEER)


def test_send_cts_during_burst_replaces_window():
    """A CTS while a paced burst is going out restarts from the packet it asks
    for, as a request for retransmission."""
    s = Station(minimum_tp_rts_cts_dt_interval=0.2)
    try:
        data = start_send(s, 2000)
        s.feed(cm_id(PEER, LOCAL), cts(5, 1))
        s.expect(cm_id(LOCAL, PEER), dpo(5, 0))
        s.expect(dt_id(LOCAL, PEER), [1] + data[0:7])
        s.feed(cm_id(PEER, LOCAL), cts(2, 1))
        s.expect(cm_id(LOCAL, PEER), dpo(2, 0))
        s.expect(dt_id(LOCAL, PEER), [1] + data[0:7])
        s.expect(dt_id(LOCAL, PEER), [2] + data[7:14])
        s.quiet(0.5)
        assert s.etp.has_send_session(LOCAL, PEER)
    finally:
        s.stop()


def test_control_message_retried(station):
    """A CTS that fails to send is tried again."""
    failures = [RuntimeError("bus busy"), RuntimeError("bus busy")]
    send = station.ecu.j1939_dll.etp._ISO11783_ETP__send_message

    def flaky(can_id, extended_id, data, fd_format=False):
        if failures:
            raise failures.pop()
        send(can_id, extended_id, data)

    station.ecu.j1939_dll.etp._ISO11783_ETP__send_message = flaky
    start_receive(station, 2000, 16)


def test_send_early_eom_aborts(station):
    start_send(station, 2000)
    station.feed(cm_id(PEER, LOCAL), eom(2000))
    station.expect(cm_id(LOCAL, PEER), abort(R.ANY_OTHER_REASON))
    assert not station.etp.has_send_session(LOCAL, PEER)
    assert station.received.empty()


def test_send_full_message_and_eom(station):
    """Several CTS windows, the last one shorter, then EOM_ACK."""
    size = 1792  # 256 packets, the last one full
    data = start_send(station, size)
    for first in range(1, 257, 100):
        count = min(100, 257 - first)
        station.feed(cm_id(PEER, LOCAL), cts(count, first))
        station.expect(cm_id(LOCAL, PEER), dpo(count, first - 1))
        for sequence in range(1, count + 1):
            number = first - 1 + sequence
            station.expect(dt_id(LOCAL, PEER), [sequence] + data[(number - 1) * 7:number * 7])
    station.feed(cm_id(PEER, LOCAL), eom(size))
    assert station.received.get(timeout=1.0) == (PGN, PEER, eom(size))
    station.quiet(0.2)
    assert not station.etp.has_send_session(LOCAL, PEER)


# --- receiving ---------------------------------------------------------------

def test_receive_times_out_without_dpo(station):
    start_receive(station, 2000, 16)
    station.quiet(1.1)
    station.expect(cm_id(LOCAL, PEER), abort(R.TIMEOUT), timeout=0.5)
    assert not station.etp.has_receive_session(PEER, LOCAL)


def test_receive_times_out_between_packets(station):
    data = payload_of(2000)
    start_receive(station, 2000, 16)
    station.feed(cm_id(PEER, LOCAL), dpo(16, 0))
    station.feed(dt_id(PEER, LOCAL), [1] + data[0:7])
    station.quiet(0.6)
    station.expect(cm_id(LOCAL, PEER), abort(R.TIMEOUT), timeout=0.5)


def test_receive_default_requests_16_packets(station):
    start_receive(station, 2000, 16)


def test_receive_abort_from_sender_ends_receive(station):
    start_receive(station, 2000, 16)
    station.feed(cm_id(PEER, LOCAL), abort(R.RESOURCES))
    assert not station.etp.has_receive_session(PEER, LOCAL)
    station.quiet(1.4)


def test_receive_abort_for_other_pgn_is_ignored(station):
    start_receive(station, 2000, 16)
    station.feed(cm_id(PEER, LOCAL), abort(R.RESOURCES, OTHER_PGN))
    assert station.etp.has_receive_session(PEER, LOCAL)


def test_receive_duplicate_dt_aborts(station):
    data = payload_of(2000)
    start_receive(station, 2000, 16)
    station.feed(cm_id(PEER, LOCAL), dpo(16, 0))
    station.feed(dt_id(PEER, LOCAL), [1] + data[0:7])
    station.feed(dt_id(PEER, LOCAL), [2] + data[7:14])
    station.feed(dt_id(PEER, LOCAL), [2] + data[7:14])
    station.expect(cm_id(LOCAL, PEER), abort(R.DUPLICATE_SEQUENCE))


def test_receive_dpo_larger_than_latest_cts_aborts():
    s = Station(max_etp_cmdt_packets=200)
    try:
        size = 1800  # 258 packets: windows of 200 and 58
        data = payload_of(size)
        start_receive(s, size, 200)
        s.feed(cm_id(PEER, LOCAL), dpo(200, 0))
        for sequence in range(1, 201):
            s.feed(dt_id(PEER, LOCAL), [sequence] + data[(sequence - 1) * 7:sequence * 7])
        s.expect(cm_id(LOCAL, PEER), cts(58, 201))
        s.feed(cm_id(PEER, LOCAL), dpo(100, 200))
        s.expect(cm_id(LOCAL, PEER), abort(R.DPO_NUM_PACKETS_GT_CTS))
    finally:
        s.stop()


def test_receive_shorter_dpo_than_cts(station):
    """A DPO for fewer packets than the CTS allowed is followed by a new CTS."""
    data = payload_of(2000)
    start_receive(station, 2000, 16)
    station.feed(cm_id(PEER, LOCAL), dpo(4, 0))
    for sequence in range(1, 5):
        station.feed(dt_id(PEER, LOCAL), [sequence] + data[(sequence - 1) * 7:sequence * 7])
    station.expect(cm_id(LOCAL, PEER), cts(16, 5))


def test_receive_rts_to_global_is_ignored(station):
    station.feed(cm_id(PEER, 0xFF), rts(2000))
    station.feed(dt_id(PEER, 0xFF), [1] + payload_of(7))
    station.quiet(0.3)
    assert not station.etp.has_receive_session(PEER, 0xFF)


def test_receive_rts_while_tp_open_aborts_busy(station):
    tp_cm = (7 << 26) | (0xEC << 16) | (LOCAL << 8) | PEER
    station.feed(tp_cm, [16, 20, 0, 3, 255] + _u24(PGN))
    station.skip(1)  # TP.CM CTS
    station.feed(cm_id(PEER, LOCAL), rts(2000))
    station.expect(cm_id(LOCAL, PEER), abort(R.BUSY))


# --- TP / ETP selection ------------------------------------------------------

def test_tp_up_to_1785_bytes(station):
    assert station.ecu.send_pgn(0, PGN >> 8, PEER, 6, LOCAL, payload_of(1785))
    can_id, data = station.frames.get(timeout=1.0)
    assert (can_id >> 16) & 0xFF == 0xEC and data[0] == 16


def test_etp_from_1786_bytes(station):
    start_send(station, 1786)


def test_broadcast_over_1785_bytes_refused(station):
    assert not station.ecu.send_pgn(0, 0xFE, 0xB0, 6, LOCAL, payload_of(1786))
    station.quiet(0.2)


def test_tp_and_etp_to_one_peer_collide(station):
    assert station.ecu.send_pgn(0, PGN >> 8, PEER, 6, LOCAL, payload_of(100))
    station.skip(1)
    assert not station.ecu.send_pgn(0, PGN >> 8, PEER, 6, LOCAL, payload_of(2000))


def test_tp_and_etp_to_different_peers(station):
    assert station.ecu.send_pgn(0, PGN >> 8, PEER, 6, LOCAL, payload_of(100))
    station.skip(1)
    assert station.ecu.send_pgn(0, PGN >> 8, PEER + 1, 6, LOCAL, payload_of(2000))


def test_has_send_session(station):
    assert not station.ecu.has_send_session(LOCAL, PEER)
    assert station.ecu.send_pgn(0, PGN >> 8, PEER, 6, LOCAL, payload_of(100))
    assert station.ecu.has_send_session(LOCAL, PEER)
    station.skip(1)
    assert station.ecu.send_pgn(0, PGN >> 8, PEER + 1, 6, LOCAL, payload_of(2000))
    assert station.ecu.has_send_session(LOCAL, PEER + 1)
    station.skip(1)
    station.feed(cm_id(PEER + 1, LOCAL), abort(R.RESOURCES))
    station.quiet(0.2)
    assert not station.ecu.has_send_session(LOCAL, PEER + 1)


def test_drop_sessions_on_address_loss(station):
    start_send(station, 2000)
    station.feed(cm_id(PEER, LOCAL), rts(2000, OTHER_PGN))
    station.skip(1)
    station.ecu.j1939_dll.drop_sessions(LOCAL)
    assert not station.etp.has_send_session(LOCAL, PEER)
    assert not station.etp.has_receive_session(PEER, LOCAL)
    station.quiet(1.4)


# --- loopback ----------------------------------------------------------------

class Loopback:
    """Two ECUs, each one's frames delivered to the other on its own thread."""

    def __init__(self, **ecu_kwargs):
        self.received = queue.Queue()
        self.a = j1939.ElectronicControlUnit(send_message=self._sender(lambda: self.b), **ecu_kwargs)
        self.b = j1939.ElectronicControlUnit(send_message=self._sender(lambda: self.a), **ecu_kwargs)
        self.a.subscribe(lambda *args: None, device_address=LOCAL)
        self.b.subscribe(self._on_message, device_address=PEER)

    def _sender(self, target):
        frames = queue.Queue()

        def deliver():
            while True:
                frame = frames.get()
                if frame is None:
                    return
                target().notify(frame[0], frame[1], time.time())

        thread = threading.Thread(target=deliver, daemon=True)
        thread.start()
        self.__dict__.setdefault('_queues', []).append(frames)

        def send(can_id, extended_id, data, fd_format=False):
            frames.put((can_id, list(data)))
        return send

    def _on_message(self, priority, pgn, sa, timestamp, data):
        if pgn == PGN and sa == LOCAL:
            self.received.put(list(data))

    def stop(self):
        for frames in self._queues:
            frames.put(None)
        self.a.stop()
        self.b.stop()


@pytest.mark.parametrize("size", [1786, 1792, 4000, 20000])
def test_loopback_transfer(size):
    link = Loopback()
    try:
        data = payload_of(size)
        assert link.a.send_pgn(0, PGN >> 8, PEER, 6, LOCAL, bytes(data))
        assert link.received.get(timeout=10.0) == data
    finally:
        link.stop()


def test_loopback_large_transfer_is_linear():
    """200 kB must not take quadratic time to frame."""
    link = Loopback(max_etp_cmdt_packets=255)
    try:
        data = payload_of(200_000)
        started = time.time()
        assert link.a.send_pgn(0, PGN >> 8, PEER, 6, LOCAL, data)
        assert link.received.get(timeout=30.0) == data
        assert time.time() - started < 15.0
    finally:
        link.stop()
