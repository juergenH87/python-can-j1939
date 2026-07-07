from __future__ import annotations

import heapq
import logging
import queue
import threading
import time

import can
from can import Listener

from .controller_application import ControllerApplication
from .j1939_21 import J1939_21
from .j1939_22 import J1939_22
from .message_id import FrameFormat
from .parameter_group_number import ParameterGroupNumber

logger = logging.getLogger(__name__)

class ElectronicControlUnit:
    """ElectronicControlUnit (ECU) holding one or more ControllerApplications (CAs)."""


    def __init__(self, data_link_layer='j1939-21', max_cmdt_packets=1, minimum_tp_rts_cts_dt_interval=None, minimum_tp_bam_dt_interval=None, send_message=None):
        """
        :param data_link_layer:
            specify data-link-layer, 'j1939-21' or 'j1939-22'
        """
        if send_message:
            self.send_message = send_message

        #: A python-can :class:`can.BusABC` instance
        self._bus = None
        # Locking object for send
        self._send_lock = threading.Lock()

        if max_cmdt_packets > 0xFF:
            raise ValueError("max number of segments that can be sent is 0xFF")

        # set data link layer
        if data_link_layer == 'j1939-21':
            self.j1939_dll = J1939_21(self.send_message, self._protocol_wakeup, self._notify_subscribers, max_cmdt_packets, minimum_tp_rts_cts_dt_interval, minimum_tp_bam_dt_interval, self._is_message_acceptable)
        elif data_link_layer == 'j1939-22':
            self.j1939_dll = J1939_22(self.send_message, self._protocol_wakeup, self._notify_subscribers, max_cmdt_packets, minimum_tp_rts_cts_dt_interval, minimum_tp_bam_dt_interval, self._is_message_acceptable)
        else:
            raise ValueError("either 'j1939-21' or 'j1939-22' must be provided for data link layer")

        #: Includes at least MessageListener.
        self._listeners = [MessageListener(self)]
        self._notifier = None

        self._subscribers = []
        self._subscribers_lock = threading.RLock()

        # Heap-based timer event list: (deadline, seq, callback, cookie, delta_time)
        self._timer_events = []
        self._timer_seq = 0
        self._timer_events_lock = threading.RLock()

        # Dependent lifecycle registry.  Any object that needs to be stopped before the ECU's own threads should be registered here. See :meth:`register_dependent`.
        self._dependents = []
        self._dependents_lock = threading.RLock()
        self._stopping = False

        self._job_thread_end = threading.Event()

        # Protocol thread: owns TP/BAM timeout management only — no user callbacks
        logger.info("Starting ECU protocol thread")
        self._protocol_wakeup_queue = queue.Queue()
        self._protocol_thread = threading.Thread(
            target=self._protocol_job_thread, name='j1939.ecu protocol_thread')
        self._protocol_thread.daemon = True

        # Timer thread: owns application cyclic callbacks only
        logger.info("Starting ECU timer thread")
        self._timer_wakeup_queue = queue.Queue()
        self._timer_thread = threading.Thread(
            target=self._timer_job_thread, name='j1939.ecu timer_thread')
        self._timer_thread.daemon = True

        self._protocol_thread.start()
        self._timer_thread.start()


    def stop(self):
        """Stops the ECU background handling

        This Function explicitly stops the background handling of the ECU.

        Before stopping the ECU's own protocol/timer threads, every registered
        dependent (see :meth:`register_dependent`) has its ``stop()`` method
        invoked in LIFO order. Exceptions raised by a dependent's ``stop()``
        are logged and swallowed so a single misbehaving dependent cannot
        prevent the rest of the shutdown from completing.
        """
        # Snapshot dependents under lock, then mark the ECU as stopping so any
        # late registrations are rejected.
        with self._dependents_lock:
            self._stopping = True
            dependents = list(self._dependents)
            self._dependents.clear()

        # LIFO: most-recently registered first.
        for dep in reversed(dependents):
            try:
                dep.stop()
            except Exception:
                logger.exception("Error stopping dependent %r", dep)

        self._job_thread_end.set()
        self._protocol_wakeup_queue.put(1)
        self._timer_wakeup_queue.put(1)
        self._protocol_thread.join()
        self._timer_thread.join()

    def register_dependent(self, dependent):
        """Register a helper whose ``stop()`` should be called by :meth:`stop`.

        Any helper object that owns threads, timers, or other resources tied
        to this ECU should call this during construction. ``ecu.stop()`` will
        invoke ``dependent.stop()`` in LIFO order before tearing down its own
        threads.

        Duplicate registrations of the same object (by identity) are silently
        ignored.

        :param dependent:
            Any object exposing a no-arg ``stop()`` method.

        :raises RuntimeError:
            If called while the ECU is shutting down.
        :raises TypeError:
            If ``dependent`` does not expose a callable ``stop`` attribute.
        """
        if not callable(getattr(dependent, 'stop', None)):
            raise TypeError(
                "dependent must expose a callable stop() method")
        with self._dependents_lock:
            if self._stopping:
                raise RuntimeError(
                    "Cannot register a dependent while the ECU is stopping")
            for existing in self._dependents:
                if existing is dependent:
                    return
            self._dependents.append(dependent)

    def unregister_dependent(self, dependent):
        """Remove a previously-registered dependent.

        :param dependent:
            The object previously passed to :meth:`register_dependent`.
        """
        with self._dependents_lock:
            self._dependents = [
                d for d in self._dependents if d is not dependent]

    def add_timer(self, delta_time, callback, cookie=None):
        """Adds a callback to the list of timer events

        :param delta_time:
            The time in seconds after which the event is to be triggered.
        :param callback:
            The callback function to call
        """
        deadline = time.monotonic() + delta_time
        with self._timer_events_lock:
            heapq.heappush(self._timer_events,
                           (deadline, self._timer_seq, callback, cookie, delta_time))
            self._timer_seq += 1
        self._timer_wakeup_queue.put(1)

    def remove_timer(self, callback):
        """Removes ALL entries from the timer event list for the given callback

        :param callback:
            The callback to be removed from the timer event list
        """
        with self._timer_events_lock:
            self._timer_events = [e for e in self._timer_events if e[2] != callback]
            heapq.heapify(self._timer_events)
        self._timer_wakeup_queue.put(1)

    def connect(self, *args, **kwargs):
        """Connect to CAN bus using python-can.

        Arguments are passed directly to :class:`can.BusABC`. Typically these
        may include:

        :param channel:
            Backend specific channel for the CAN interface.
        :param str interface:
            Name of the interface (formerly ``bustype``, renamed in python-can v4.2). See
            `python-can manual <https://python-can.readthedocs.io/en/latest/configuration.html#interface-names>`__
            for full list of supported interfaces.
        :param int bitrate:
            Bitrate in bit/s.

        :raises can.CanError:
            When connection fails.
        """
        self._bus = can.interface.Bus(*args, **kwargs)
        logger.info("Connected to '%s'", self._bus.channel_info)
        self._notifier = can.Notifier(self._bus, self._listeners, 1)
        return self._bus

    def disconnect(self):
        """Disconnect from the CAN bus.

        Must be overridden in a subclass if a custom interface is used.
        """
        if self._notifier is None:
            raise RuntimeError("notifier is not set; call connect() before disconnect()")
        if self._bus is None:
            raise RuntimeError("bus is not set; call connect() before disconnect()")
        self._notifier.stop()
        self._bus.shutdown()
        self._bus = None

    def subscribe(self, callback, device_address=None):
        """Add the given callback to the message notification stream.

        :param callback:
            Function to call when message is received.
        :param int device_address:
            Device address of the application.
            This is a simple way for peer-to-peer reception without adding a controller-application.
            Only one device address can be entered. Multiple device addresses are only possible with controller applications.
            Note: TP.CMDT will only be received if the destination address is bound to a controller application.
        """
        with self._subscribers_lock:
            self._subscribers.append({'cb': callback, 'dev_adr': device_address})

    def unsubscribe(self, callback):
        """Stop listening for message.

        :param callback:
            Function to call when message is received.
        """
        with self._subscribers_lock:
            self._subscribers = [d for d in self._subscribers if d['cb'] != callback]


    def add_ca(self, **kwargs):
        """Add a ControllerApplication to the ECU.

        :param controller_application:
            A :class:`j1939.ControllerApplication` object.

        :param name:
            A :class:`j1939.Name` object.

        :param device_address:
            An integer representing the device address to announce to the bus.

        :return:
            The CA object that was added.

        :rtype: r3964.ControllerApplication
        """
        if 'controller_application' in kwargs:
            ca = kwargs['controller_application']
        else:
            if 'name' not in kwargs:
                raise ValueError("either 'controller_application' or 'name' must be provided")
            name = kwargs.get('name')
            da = kwargs.get('device_address', None)
            ca = ControllerApplication(name, da)

        self.j1939_dll.add_ca(ca)
        ca.associate_ecu(self)
        return ca

    def remove_ca(self, device_address):
        """Remove a ControllerApplication from the ECU.

        :param int device_address:
            A integer representing the device address

        :return:
            True if the ControllerApplication was successfully removed, otherwise False is returned.
        """
        return self.j1939_dll.remove_ca(device_address)

    def add_bus(self, bus):
        """Add a bus to the ECU.

        :param bus:
            A :class:`can.BusABC` object.
        """
        self._bus = bus

    def add_notifier(self, notifier):
        """Add a notifier to the ECU.

        :param notifier:
            A :class:`can.Notifier` object.
        """
        self._notifier = notifier
        for listener in self._listeners:
            self._notifier.add_listener(listener)

    def remove_bus(self):
        """Remove the bus from the ECU.
        """
        self._bus = None

    def remove_notifier(self):
        """Remove the notifier from the ECU.
        """
        if self._notifier is None:
            return
        for listener in self._listeners:
            self._notifier.remove_listener(listener)
        self._notifier = None

    def send_pgn(self, data_page, pdu_format, pdu_specific, priority, src_address, data, time_limit=0, frame_format=FrameFormat.FEFF):
        """send a pgn
        :param int data_page: data page
        :param int pdu_format: pdu format
        :param int pdu_specific: pdu specific
        :param int priority: message priority
        :param int src_address: address of the transmitter
        :param list data: payload, each list index represents one payload byte
        :param time_limit: option j1939-22 multi-pg: specify a time limit in s (e.g. 0.1 == 100ms),
        after this time, the multi-pg will be sent. several pgs can thus be combined in one multi-pg.
        0 or no time-limit means immediate sending.
        """
        return self.j1939_dll.send_pgn(data_page, pdu_format, pdu_specific, priority, src_address, data, time_limit, frame_format)

    def send_message(self, can_id, extended_id, data, fd_format=False):
        """Send a raw CAN message to the bus.

        This method may be overridden in a subclass if you need to integrate
        this library with a custom backend.
        It is safe to call this from multiple threads.

        :param int can_id:
            CAN-ID of the message (always 29-bit)
        :param data:
            Data to be transmitted (anything that can be converted to bytes)
        :param fd_format:
            fd format means bitrate switching and payload of max 64Bytes is active

        :raises can.CanError:
            When the message fails to be transmitted
        """

        if not self._bus:
            raise RuntimeError("Not connected to CAN bus")
        msg = can.Message(is_extended_id=extended_id,
                          arbitration_id=can_id,
                          data=data,
                          is_fd=fd_format,
                          bitrate_switch=fd_format
                          )
        with self._send_lock:
            self._bus.send(msg)
        # TODO: check error receivement

    def notify(self, can_id, data, timestamp):
        """Feed incoming CAN message into this ecu.

        If a custom interface is used, this function must be called for each
        29-bit standard message read from the CAN bus.

        :param int can_id:
            CAN-ID of the message (always 29-bit)
        :param bytearray data:
            Data part of the message (0 - 8 bytes)
        :param float timestamp:
            The timestamp field in a CAN message is a floating point number
            representing when the message was received since the epoch in
            seconds.
            Where possible this will be timestamped in hardware.
        """
        self.j1939_dll.notify(can_id, data, timestamp)

    def add_bus_filters(self, filters: can.typechecking.CanFilters | None):
        """Add bus filters to the underlying CAN bus.

         :param filters:
            An iterable of dictionaries each containing a "can_id",
            a "can_mask", and an optional "extended" key
        """
        if self._bus is None:
            raise RuntimeError("Not connected to CAN bus")
        self._bus.set_filters(filters)

    def _protocol_job_thread(self):
        """Protocol thread: handles TP/BAM timeout management only.

        This thread is isolated from application timer callbacks so that slow
        user callbacks cannot delay protocol-level timeouts (which would cause
        spurious ABORT messages on the bus).
        """
        while not self._job_thread_end.is_set():
            now = time.monotonic()
            next_wakeup = self.j1939_dll.async_job_thread(now)
            time_to_sleep = next_wakeup - time.monotonic()
            if time_to_sleep > 0:
                try:
                    self._protocol_wakeup_queue.get(True, time_to_sleep)
                except queue.Empty:
                    pass

    def _timer_job_thread(self):
        """Timer thread: handles application cyclic callbacks only.

        Uses a heapq (min-heap keyed by deadline) for O(log n) scheduling.
        Woken early via _timer_wakeup_queue whenever a timer is added/removed.
        Callbacks returning True are rescheduled; returning False are removed.
        """
        while not self._job_thread_end.is_set():
            now = time.monotonic()
            next_wakeup = now + 5.0

            with self._timer_events_lock:
                while self._timer_events and self._timer_events[0][0] <= now:
                    deadline, seq, cb, cookie, delta = heapq.heappop(self._timer_events)
                    logger.debug("Deadline for timer event reached")
                    try:
                        reschedule = (cb(cookie) is True)
                    except Exception:
                        #TODO: is there a better way to handle exceptions in user callbacks?  
                        # We don't want one bad callback to break the timer thread, 
                        # but we also don't want to just swallow it silently.
                        logger.exception("Timer callback failed: %r", cb)
                        reschedule = False
                    if reschedule:
                        # reschedule: advance deadline past now to avoid burst catch-up
                        new_deadline = deadline + delta
                        while new_deadline < now:
                            new_deadline += delta
                        heapq.heappush(self._timer_events,
                                       (new_deadline, self._timer_seq, cb, cookie, delta))
                        self._timer_seq += 1
                    # returning False (or None) means remove — already popped, nothing to do

                if self._timer_events:
                    next_wakeup = self._timer_events[0][0]

            time_to_sleep = next_wakeup - time.monotonic()
            if time_to_sleep > 0:
                try:
                    self._timer_wakeup_queue.get(True, time_to_sleep)
                except queue.Empty:
                    pass

    def _protocol_wakeup(self):
        """Wakeup the protocol job thread.

        Called by the DLL (j1939_21/j1939_22) when TP state changes require
        immediate re-evaluation of protocol deadlines.
        """
        self._protocol_wakeup_queue.put(1)

    def _notify_subscribers(self, priority, pgn, sa, dest, timestamp, data):
        """Feed incoming message to subscribers.

        :param int priority:
            Priority of the message
        :param int pgn:
            Parameter Group Number of the message
        :param int sa:
            Source Address of the message
        :param int dest:
            Destination Address of the message
        :param int timestamp:
            Timestamp of the CAN message
        :param bytearray data:
            Data of the PDU
        """
        logger.debug(f"notify subscribers for PGN {pgn}")
        # Snapshot under lock so subscribe/unsubscribe from any thread is safe.
        with self._subscribers_lock:
            snapshot = list(self._subscribers)
        for dic in snapshot:
            if (dic['dev_adr'] is None) or (dest == ParameterGroupNumber.Address.GLOBAL) or (callable(dic['dev_adr']) and dic['dev_adr'](dest)) or (dest == dic['dev_adr']):
                dic['cb'](priority, pgn, sa, timestamp, data)

    def _is_message_acceptable(self, dest):
        # Ownership / active-participation check only: does a subscriber own this
        # exact destination address (simple peer-to-peer reception)? This gate
        # decides whether the stack actively engages the directed transport
        # protocol (RTS/CTS/EOM-ACK). Passive wildcard (``device_address=None``)
        # and callable subscribers are handled separately by _notify_subscribers()
        # so a monitor never causes the stack to answer on the bus.
        with self._subscribers_lock:
            return any(d['dev_adr'] == dest for d in self._subscribers)

class MessageListener(Listener):
    """Listens for messages on CAN bus and feeds them to an ECU instance.

    :param j1939.ElectronicControlUnit ecu:
        The ECU to notify on new messages.
    """

    def __init__(self, ecu : ElectronicControlUnit):
        self.ecu = ecu
        self.stopped = False

    def on_message_received(self, msg : can.Message):
        if self.stopped or msg.is_error_frame or msg.is_remote_frame or (not msg.is_extended_id):
            return

        try:
            self.ecu.notify(msg.arbitration_id, msg.data, msg.timestamp)
        except Exception as e:
            # Exceptions in any callbaks should not affect CAN processing
            logger.error(str(e))

    def stop(self):
        self.stopped = True
