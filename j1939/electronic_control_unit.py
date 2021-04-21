import logging
import can
from can import Listener
import time
import threading

try:
    # Python27
    import Queue as queue
except ImportError:
    # Python35
    import queue

import j1939

logger = logging.getLogger(__name__)

class ElectronicControlUnit:
    """ElectronicControlUnit (ECU) holding one or more ControllerApplications (CAs)."""

    class ConnectionMode:
        RTS = 16
        CTS = 17
        EOM_ACK = 19
        BAM = 32
        ABORT = 255

    class ConnectionAbortReason:
        BUSY = 1        # Already  in  one  or  more  connection  managed  sessions  and  cannot  support another
        RESOURCES = 2   # System  resources  were  needed  for  another  task  so  this  connection  managed session was terminated
        TIMEOUT = 3     # A timeout occured
        # 4..250 Reserved by SAE
        CTS_WHILE_DT = 4  # according AUTOSAR: CTS messages received when data transfer is in progress
        # 251..255 Per J1939/71 definitions - but there are none?

    class Timeout:
        """Timeouts according SAE J1939/21"""
        Tr = 0.200 # Response Time
        Th = 0.500 # Holding Time
        T1 = 0.750
        T2 = 1.250
        T3 = 1.250
        T4 = 1.050
        # timeout for multi packet broadcast messages 50..200ms
        Tb = 0.050

    class SendBufferState:
        WAITING_CTS = 0        # waiting for CTS
        SENDING_IN_CTS = 1     # sending packages (temporary state)
        SENDING_BM = 2         # sending broadcast packages

    def __init__(self, bus=None, max_cmdt_packets=1):
        """
        :param can.BusABC bus:
            A python-can bus instance to re-use.
        """
        #: A python-can :class:`can.BusABC` instance
        self._bus = bus
        # Locking object for send
        self._send_lock = threading.Lock()

        # number of packets that can be sent/received with CMDT (Connection Mode Data Transfer)
        self._max_cmdt_packets = max_cmdt_packets

        #: Includes at least MessageListener.
        self._listeners = [MessageListener(self)]
        self._notifier = None
        self._subscribers = []
        # List of ControllerApplication
        self._cas = []
        # Receive buffers
        self._rcv_buffer = {}
        # Send buffers
        self._snd_buffer = {}
        # List of timer events the job thread should care of
        self._timer_events = []

        self._job_thread_end = threading.Event()
        logger.info("Starting ECU async thread")
        self._job_thread_wakeup_queue = queue.Queue()
        self._job_thread = threading.Thread(target=self._async_job_thread, name='j1939.ecu job_thread')
        # A thread can be flagged as a "daemon thread". The significance of
        # this flag is that the entire Python program exits when only daemon
        # threads are left.
        self._job_thread.daemon = True
        self._job_thread.start()
        # TODO: do we have to stop the tread somehow?

    def _async_job_thread(self):
        """Asynchronous thread for handling various jobs

        This Thread handles various tasks:
        - Event trigger for associated CAs
        - Timeout monitoring of communication objects

        To construct a blocking wait with timeout the task waits on a
        queue-object. When other tasks are adding timer-events they can
        wakeup the timeout handler to recalculate the new sleep-time
        to awake at the new events.
        """
        while not self._job_thread_end.isSet():
            now = time.time()
            next_wakeup = time.time() + 5.0 # wakeup in 5 seconds

            # check receive buffers for timeout
            # using "list(x)" to prevent "RuntimeError: dictionary changed size during iteration"
            for bufid in list(self._rcv_buffer):
                buf = self._rcv_buffer[bufid]
                if buf['deadline'] != 0:
                    if buf['deadline'] > now:
                        if next_wakeup > buf['deadline']:
                            next_wakeup = buf['deadline']
                    else:
                        # deadline reached
                        logger.info("Deadline reached for rcv_buffer src 0x%02X dst 0x%02X", buf['src_address'], buf['dest_address'] )
                        if buf['dest_address'] != j1939.ParameterGroupNumber.Address.GLOBAL:
                            # TODO: should we handle retries?
                            self.send_tp_abort(buf['dest_address'], buf['src_address'], ElectronicControlUnit.ConnectionAbortReason.TIMEOUT, buf['pgn'])
                        # TODO: should we notify our CAs about the cancelled transfer?
                        del self._rcv_buffer[bufid]

            # check send buffers
            # using "list(x)" to prevent "RuntimeError: dictionary changed size during iteration"
            for bufid in list(self._snd_buffer):
                buf = self._snd_buffer[bufid]
                if buf['deadline'] != 0:
                    if buf['deadline'] > now:
                        if next_wakeup > buf['deadline']:
                            next_wakeup = buf['deadline']
                    else:
                        # deadline reached
                        if buf['state'] == ElectronicControlUnit.SendBufferState.WAITING_CTS:
                            logger.info("Deadline WAITING_CTS reached for snd_buffer src 0x%02X dst 0x%02X", buf['src_address'], buf['dest_address'] )
                            self.send_tp_abort(buf['src_address'], buf['dest_address'], ElectronicControlUnit.ConnectionAbortReason.TIMEOUT, buf['pgn'])
                            # TODO: should we notify our CAs about the cancelled transfer?
                            del self._snd_buffer[bufid]
                        elif buf['state'] == ElectronicControlUnit.SendBufferState.SENDING_IN_CTS:
                            # do not care about deadlines while sending (from within other function)
                            # TODO: maybe we can implement an asynchronous send queue here?
                            pass
                        elif buf['state'] == ElectronicControlUnit.SendBufferState.SENDING_BM:
                            # send next broadcast message...
                            offset = buf['next_packet_to_send'] * 7
                            data = buf['data'][offset:]
                            if len(data)>7:
                                data = data[:7]
                            else:
                                while len(data)<7:
                                    data.append(255)
                            data.insert(0, buf['next_packet_to_send']+1)
                            self.send_tp_dt(buf['src_address'], buf['dest_address'], data)
                            buf['next_packet_to_send'] += 1

                            if buf['next_packet_to_send'] < buf['num_packages']:
                                buf['deadline'] = time.time() + ElectronicControlUnit.Timeout.Tb
                                # recalc next wakeup
                                if next_wakeup > buf['deadline']:
                                    next_wakeup = buf['deadline']
                            else:
                                # done
                                del self._snd_buffer[bufid]
                        else:
                            logger.critical("unknown SendBufferState %d", buf['state'])
                            del self._snd_buffer[bufid]

            # check timer events
            for event in self._timer_events:
                if event['deadline'] > now:
                    if next_wakeup > event['deadline']:
                        next_wakeup = event['deadline']
                else:
                    # deadline reached
                    logger.debug("Deadline for event reached")
                    if event['callback']( event['cookie'] ) == True:
                        # "true" means the callback wants to be called again
                        while event['deadline'] < now:
                            # just to take care of overruns
                            event['deadline'] += event['delta_time']
                        # recalc next wakeup
                        if next_wakeup > event['deadline']:
                            next_wakeup = event['deadline']
                    else:
                        # remove from list
                        self._timer_events.remove( event )

            time_to_sleep = next_wakeup - time.time()
            if time_to_sleep > 0:
                try:
                    self._job_thread_wakeup_queue.get(True, time_to_sleep)
                except queue.Empty:
                    # do nothing
                    pass

    def stop(self):
        """Stops the ECU background handling

        This Function explicitely stops the background handling of the ECU.
        """
        self._job_thread_end.set()
        self._job_thread_wakeup()
        self._job_thread.join()

    def _job_thread_wakeup(self):
        """Wakeup the async job thread

        By calling this function we wakeup the asyncronous job thread to
        force a recalculation of his next wakeup event.
        """
        self._job_thread_wakeup_queue.put(1)

    def add_timer(self, delta_time, callback, cookie=None):
        """Adds a callback to the list of timer events

        :param delta_time:
            The time in seconds after which the event is to be triggered.
        :param callback:
            The callback function to call
        """

        d = {
            'delta_time': delta_time,
            'callback': callback,
            'deadline': (time.time() + delta_time),
            'cookie': cookie,
            }

        self._timer_events.append( d )
        self._job_thread_wakeup()

    def remove_timer(self, callback):
        """Removes ALL entries from the timer event list for the given callback

        :param callback:
            The callback to be removed from the timer event list
        """
        for event in self._timer_events:
            if event['callback'] == callback:
                self._timer_events.remove( event )
        self._job_thread_wakeup()

    def connect(self, *args, **kwargs):
        """Connect to CAN bus using python-can.

        Arguments are passed directly to :class:`can.BusABC`. Typically these
        may include:

        :param channel:
            Backend specific channel for the CAN interface.
        :param str bustype:
            Name of the interface. See
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

    def disconnect(self):
        """Disconnect from the CAN bus.

        Must be overridden in a subclass if a custom interface is used.
        """
        self._notifier.stop()
        self._bus.shutdown()
        self._bus = None

    def subscribe(self, callback, device_address=None):
        """Add the given callback to the message notification stream.

        :param callback:
            Function to call when message is received.
        :param int device_address:
            Device address of the application
            The address which the message is intended

            if device_address is set to None or not entered, each message is received
            (except: TP.CMDT is only received if the destination address is bound to a controller application)
        """
        self._subscribers.append({'cb': callback, 'dev_adr':device_address})

    def unsubscribe(self, callback):
        """Stop listening for message.

        :param callback:
            Function to call when message is received.
        """
        for dic in self._subscribers:
            if dic['cb'] == callback:
                self._subscribers.remove(dic)

    def _buffer_hash(self, src_address, dest_address):
        """Calcluates a hash value for the given address pair

        :param src_address:
            The Source-Address the connection should bound to.
        :param dest_address:
            The Destination-Address the connection should bound to.

        :return:
            The calculated hash value.

        :rtype: int
        """
        return ((src_address & 0xFF) << 8) | (dest_address & 0xFF)


    def _process_tp_cm(self, mid, dest_address, data, timestamp):
        """Processes a Transport Protocol Connection Management (TP.CM) message

        :param j1939.MessageId mid:
            A MessageId object holding the information extracted from the can_id.
        :param int dest_address:
            The destination address of the message
        :param bytearray data:
            The data contained in the can-message.
        :param float timestamp:
            The timestamp the message was received (mostly) in fractions of Epoch-Seconds.
        """
        control_byte = data[0]
        pgn = data[5] | (data[6] << 8) | (data[7] << 16)

        src_address = mid.source_address

        if control_byte == ElectronicControlUnit.ConnectionMode.RTS:
            message_size = data[1] | (data[2] << 8)
            num_packages = data[3]
            buffer_hash = self._buffer_hash(src_address, dest_address)
            if buffer_hash in self._rcv_buffer:
                # according SAE J1939-21 we have to send an ABORT if an active
                # transmission is already established
                self.send_tp_abort(dest_address, src_address, ElectronicControlUnit.ConnectionAbortReason.BUSY, pgn)
                return
            # open new buffer for this connection
            self._rcv_buffer[buffer_hash] = {
                    "pgn": pgn,
                    "message_size": message_size,
                    "num_packages": num_packages,
                    "next_packet": min(self._max_cmdt_packets, num_packages),
                    "max_cmdt_packages": self._max_cmdt_packets,
                    "data": [],
                    "deadline": time.time() + ElectronicControlUnit.Timeout.T2,
                    'src_address' : src_address,
                    'dest_address' : dest_address,
                }

            self.send_tp_cts(dest_address, src_address, self._rcv_buffer[buffer_hash]["next_packet"], 1, pgn)
            self._job_thread_wakeup()
        elif control_byte == ElectronicControlUnit.ConnectionMode.CTS:
            num_packages = data[1]
            next_package_number = data[2] - 1
            buffer_hash = self._buffer_hash(dest_address, src_address)
            if buffer_hash not in self._snd_buffer:
                self.send_tp_abort(dest_address, src_address, ElectronicControlUnit.ConnectionAbortReason.RESOURCES, pgn)
                return
            if num_packages == 0:
                # SAE J1939/21
                # receiver requests a pause
                self._snd_buffer[buffer_hash]['deadline'] = time.time() + ElectronicControlUnit.Timeout.Th
                self._job_thread_wakeup()
                return

            self._snd_buffer[buffer_hash]['deadline'] = time.time() + 10.0 # do not monitor deadlines while sending
            self._snd_buffer[buffer_hash]['state'] = ElectronicControlUnit.SendBufferState.SENDING_IN_CTS
            self._job_thread_wakeup()

            # TODO: should we send the answer packets asynchronously
            #       maybe in our _job_thread?

            for package in range(next_package_number, next_package_number + num_packages):
                offset = package * 7
                data = self._snd_buffer[buffer_hash]['data'][offset:]
                if len(data)>7:
                    data = data[:7]
                else:
                    while len(data)<7:
                        data.append(255)
                data.insert(0, package+1)
                self.send_tp_dt(dest_address, src_address, data)

            self._snd_buffer[buffer_hash]['deadline'] = time.time() + ElectronicControlUnit.Timeout.T3
            self._snd_buffer[buffer_hash]['state'] = ElectronicControlUnit.SendBufferState.WAITING_CTS
            self._job_thread_wakeup()

        elif control_byte == ElectronicControlUnit.ConnectionMode.EOM_ACK:
            buffer_hash = self._buffer_hash(dest_address, src_address)
            if buffer_hash not in self._snd_buffer:
                self.send_tp_abort(dest_address, src_address, ElectronicControlUnit.ConnectionAbortReason.RESOURCES, pgn)
                return
            # TODO: should we inform the application about the successful transmission?
            del self._snd_buffer[buffer_hash]
            self._job_thread_wakeup()
        elif control_byte == ElectronicControlUnit.ConnectionMode.BAM:
            message_size = data[1] | (data[2] << 8)
            num_packages = data[3]
            buffer_hash = self._buffer_hash(src_address, dest_address)
            if buffer_hash in self._rcv_buffer:
                # TODO: should we deliver the partly received message to our CAs?
                del self._rcv_buffer[buffer_hash]
                self._job_thread_wakeup()

            # init new buffer for this connection
            self._rcv_buffer[buffer_hash] = {
                    "pgn": pgn,
                    "message_size": message_size,
                    "num_packages": num_packages,
                    "next_packet": 1,
                    "max_cmdt_packages": self._max_cmdt_packets,
                    "data": [],
                    "deadline": time.time() + ElectronicControlUnit.Timeout.T1,
                    'src_address' : src_address,
                    'dest_address' : dest_address,
                }
            self._job_thread_wakeup()
        elif control_byte == ElectronicControlUnit.ConnectionMode.ABORT:
            # TODO
            pass
        else:
            raise RuntimeError("Received TP.CM with unknown control_byte %d", control_byte)

    def _process_tp_dt(self, mid, dest_address, data, timestamp):
        sequence_number = data[0]

        src_address = mid.source_address

        buffer_hash = self._buffer_hash(src_address, dest_address)
        if buffer_hash not in self._rcv_buffer:
            # TODO: LOG/TRACE/EXCEPTION?
            return

        # get data
        self._rcv_buffer[buffer_hash]['data'].extend(data[1:])

        # message is complete with sending an acknowledge
        if len(self._rcv_buffer[buffer_hash]['data']) >= self._rcv_buffer[buffer_hash]['message_size']:
            logger.info("finished RCV of PGN {} with size {}".format(self._rcv_buffer[buffer_hash]['pgn'], self._rcv_buffer[buffer_hash]['message_size']))
            # shorten data to message_size
            self._rcv_buffer[buffer_hash]['data'] = self._rcv_buffer[buffer_hash]['data'][:self._rcv_buffer[buffer_hash]['message_size']]
            # finished reassembly
            if dest_address != j1939.ParameterGroupNumber.Address.GLOBAL:
                self.send_tp_eom_ack(dest_address, src_address, self._rcv_buffer[buffer_hash]['message_size'], self._rcv_buffer[buffer_hash]['num_packages'], self._rcv_buffer[buffer_hash]['pgn'])
            self.notify_subscribers(mid.priority, self._rcv_buffer[buffer_hash]['pgn'], src_address, dest_address, timestamp, self._rcv_buffer[buffer_hash]['data'])
            del self._rcv_buffer[buffer_hash]
            self._job_thread_wakeup()
            return

        # clear to send
        if (dest_address != j1939.ParameterGroupNumber.Address.GLOBAL) and (sequence_number >= self._rcv_buffer[buffer_hash]['next_packet']):

            # send cts
            number_of_packets_that_can_be_sent = min( self._max_cmdt_packets,
                                                      self._rcv_buffer[buffer_hash]['num_packages'] - self._rcv_buffer[buffer_hash]['next_packet'] )
            next_packet_to_be_sent = self._rcv_buffer[buffer_hash]['next_packet'] + 1
            self.send_tp_cts(dest_address, src_address, number_of_packets_that_can_be_sent, next_packet_to_be_sent, self._rcv_buffer[buffer_hash]['pgn'])

            # calculate next packet number at which a CTS is to be sent
            self._rcv_buffer[buffer_hash]['next_packet'] = min(self._rcv_buffer[buffer_hash]['next_packet'] + self._max_cmdt_packets,
                                                               self._rcv_buffer[buffer_hash]['num_packages'])

            self._rcv_buffer[buffer_hash]['deadline'] = time.time() + ElectronicControlUnit.Timeout.T2
            self._job_thread_wakeup()
            return

        self._rcv_buffer[buffer_hash]['deadline'] = time.time() + ElectronicControlUnit.Timeout.T1
        self._job_thread_wakeup()


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

        mid = j1939.MessageId(can_id=can_id)
        pgn = j1939.ParameterGroupNumber()
        pgn.from_message_id(mid)

        if pgn.is_pdu2_format:
            # direct broadcast
            self.notify_subscribers(mid.priority, pgn.value, mid.source_address, j1939.ParameterGroupNumber.Address.GLOBAL, timestamp, data)
            return

        # peer to peer
        # pdu_specific is destination Address
        pgn_value = pgn.value & 0x1FF00
        dest_address = pgn.pdu_specific # may be Address.GLOBAL

        # iterate all CAs to check if we have to handle this destination address
        if dest_address != j1939.ParameterGroupNumber.Address.GLOBAL:
            reject = True
            for ca in self._cas:
                if ca.message_acceptable(dest_address):
                    reject = False
                    break
            if reject == True:
                return

        if pgn_value == j1939.ParameterGroupNumber.PGN.ADDRESSCLAIM:
            for ca in self._cas:
                ca._process_addressclaim(mid, data, timestamp)
        elif pgn_value == j1939.ParameterGroupNumber.PGN.REQUEST:
            for ca in self._cas:
                if ca.message_acceptable(dest_address):
                    ca._process_request(mid, dest_address, data, timestamp)
        elif pgn_value == j1939.ParameterGroupNumber.PGN.TP_CM:
            self._process_tp_cm(mid, dest_address, data, timestamp)
        elif pgn_value == j1939.ParameterGroupNumber.PGN.DATATRANSFER:
            self._process_tp_dt(mid, dest_address, data, timestamp)
        else:
            self.notify_subscribers(mid.priority, pgn_value, mid.source_address, dest_address, timestamp, data)
            return


    def notify_subscribers(self, priority, pgn, sa, dest, timestamp, data):
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
        logger.debug("notify subscribers for PGN {}".format(pgn))
        # notify only the CA for which the message is intended
        # each CA receives all broadcast messages
        for dic in self._subscribers:
            if (dic['dev_adr'] == None) or (dest == j1939.ParameterGroupNumber.Address.GLOBAL) or (dest == dic['dev_adr']):
                dic['cb'](priority, pgn, sa, timestamp, data)

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
            ca = j1939.ControllerApplication(name, da)

        self._cas.append(ca)
        ca.associate_ecu(self)
        return ca

    def remove_ca(self, device_address):
        """Remove a ControllerApplication from the ECU.

        :param int device_address:
            A integer representing the device address

        :return:
            True if the ControllerApplication was successfully removed, otherwise False is returned.
        """
        for ca in self._cas:
            if device_address == ca._device_address_preferred:
                self._cas.remove(ca)
                return True
        return False

    class Acknowledgement:
        ACK = 0
        NACK = 1
        AccessDenied = 2
        CannotRespond = 3

    def send_message(self, can_id, data):
        """Send a raw CAN message to the bus.

        This method may be overridden in a subclass if you need to integrate
        this library with a custom backend.
        It is safe to call this from multiple threads.

        :param int can_id:
            CAN-ID of the message (always 29-bit)
        :param data:
            Data to be transmitted (anything that can be converted to bytes)

        :raises can.CanError:
            When the message fails to be transmitted
        """

        if not self._bus:
            raise RuntimeError("Not connected to CAN bus")
        msg = can.Message(extended_id=True,
                          arbitration_id=can_id,
                          data=data
                          )
        with self._send_lock:
            self._bus.send(msg)
        # TODO: check error receivement

    def send_tp_dt(self, src_address, dest_address, data):
        pgn = j1939.ParameterGroupNumber(0, 235, dest_address)
        mid = j1939.MessageId(priority=7, parameter_group_number=pgn.value, source_address=src_address)
        self.send_message(mid.can_id, data)

    def send_tp_abort(self, src_address, dest_address, reason, pgn_value):
        pgn = j1939.ParameterGroupNumber(0, 236, dest_address)
        mid = j1939.MessageId(priority=7, parameter_group_number=pgn.value, source_address=src_address)
        data = [ElectronicControlUnit.ConnectionMode.ABORT, reason, 0xFF, 0xFF, 0xFF, pgn_value & 0xFF, (pgn_value >> 8) & 0xFF, (pgn_value >> 16) & 0xFF]
        self.send_message(mid.can_id, data)

    def send_tp_cts(self, src_address, dest_address, num_packets, next_packet, pgn_value):
        pgn = j1939.ParameterGroupNumber(0, 236, dest_address)
        mid = j1939.MessageId(priority=7, parameter_group_number=pgn.value, source_address=src_address)
        data = [ElectronicControlUnit.ConnectionMode.CTS, num_packets, next_packet, 0xFF, 0xFF, pgn_value & 0xFF, (pgn_value >> 8) & 0xFF, (pgn_value >> 16) & 0xFF]
        self.send_message(mid.can_id, data)

    def send_tp_eom_ack(self, src_address, dest_address, message_size, num_packets, pgn_value):
        pgn = j1939.ParameterGroupNumber(0, 236, dest_address)
        mid = j1939.MessageId(priority=7, parameter_group_number=pgn.value, source_address=src_address)
        data = [ElectronicControlUnit.ConnectionMode.EOM_ACK, message_size & 0xFF, (message_size >> 8) & 0xFF, num_packets, 0xFF, pgn_value & 0xFF, (pgn_value >> 8) & 0xFF, (pgn_value >> 16) & 0xFF]
        self.send_message(mid.can_id, data)

    def send_tp_rts(self, src_address, dest_address, priority, pgn_value, message_size, num_packets):
        pgn = j1939.ParameterGroupNumber(0, 236, dest_address)
        mid = j1939.MessageId(priority=priority, parameter_group_number=pgn.value, source_address=src_address)
        data = [ElectronicControlUnit.ConnectionMode.RTS, message_size & 0xFF, (message_size >> 8) & 0xFF, num_packets, 0xFF, pgn_value & 0xFF, (pgn_value >> 8) & 0xFF, (pgn_value >> 16) & 0xFF]
        self.send_message(mid.can_id, data)

    def send_acknowledgement(self, control_byte, group_function_value, address_acknowledged, pgn):
        data = [control_byte, group_function_value, 0xFF, 0xFF, address_acknowledged, (pgn & 0xFF), ((pgn >> 8) & 0xFF), ((pgn >> 16) & 0xFF)]
        mid = j1939.MessageId(priority=6, parameter_group_number=0x00E800, source_address=255)
        self.send_message(mid.can_id, data)

    def send_tp_bam(self, src_address, priority, pgn_value, message_size, num_packets):
        pgn = j1939.ParameterGroupNumber(0, 236, j1939.ParameterGroupNumber.Address.GLOBAL)
        mid = j1939.MessageId(priority=priority, parameter_group_number=pgn.value, source_address=src_address)
        data = [ElectronicControlUnit.ConnectionMode.BAM, message_size & 0xFF, (message_size >> 8) & 0xFF, num_packets, 0xFF, pgn_value & 0xFF, (pgn_value >> 8) & 0xFF, (pgn_value >> 16) & 0xFF]
        self.send_message(mid.can_id, data)

    def send_pgn(self, data_page, pdu_format, pdu_specific, priority, src_address, data):
        pgn = j1939.ParameterGroupNumber(data_page, pdu_format, pdu_specific)
        if len(data) <= 8:
            # send normal message
            mid = j1939.MessageId(priority=priority, parameter_group_number=pgn.value, source_address=src_address)
            self.send_message(mid.can_id, data)
        else:
            # if the PF is between 0 and 239, the message is destination dependent when pdu_specific != 255
            # if the PF is between 240 and 255, the message can only be broadcast
            if (pdu_specific == j1939.ParameterGroupNumber.Address.GLOBAL) or j1939.ParameterGroupNumber(0, pdu_format, pdu_specific).is_pdu2_format:
                dest_address = j1939.ParameterGroupNumber.Address.GLOBAL
            else:
                dest_address = pdu_specific

            # init sequence
            # known limitation: only one BAM can be sent in parallel to a destination node
            buffer_hash = self._buffer_hash(src_address, dest_address)
            if buffer_hash in self._snd_buffer:
                # There is already a sequence active for this pair
                return False
            message_size = len(data)
            num_packets = int(message_size / 7) if (message_size % 7 == 0) else int(message_size / 7) + 1

            # if the PF is between 240 and 255, the message can only be broadcast
            if dest_address == j1939.ParameterGroupNumber.Address.GLOBAL:
                # send BAM
                self.send_tp_bam(src_address, priority, pgn.value, message_size, num_packets)

                # init new buffer for this connection
                self._snd_buffer[buffer_hash] = {
                        "pgn": pgn.value,
                        "priority": priority,
                        "message_size": message_size,
                        "num_packages": num_packets,
                        "data": data,
                        "state": ElectronicControlUnit.SendBufferState.SENDING_BM,
                        "deadline": time.time() + ElectronicControlUnit.Timeout.Tb,
                        'src_address' : src_address,
                        'dest_address' : j1939.ParameterGroupNumber.Address.GLOBAL,
                        'next_packet_to_send' : 0,
                    }
            else:
                # send RTS/CTS
                # init new buffer for this connection
                self._snd_buffer[buffer_hash] = {
                        "pgn": pgn.value,
                        "priority": priority,
                        "message_size": message_size,
                        "num_packages": num_packets,
                        "data": data,
                        "state": ElectronicControlUnit.SendBufferState.WAITING_CTS,
                        "deadline": time.time() + ElectronicControlUnit.Timeout.T3,
                        'src_address' : src_address,
                        'dest_address' : pdu_specific,
                    }
                self.send_tp_rts(src_address, pdu_specific, priority, pgn.value, message_size, num_packets)

            self._job_thread_wakeup()

        return True


class MessageListener(Listener):
    """Listens for messages on CAN bus and feeds them to an ECU instance.

    :param j1939.ElectronicControlUnit ecu:
        The ECU to notify on new messages.
    """

    def __init__(self, ecu):
        self.ecu = ecu

    def on_message_received(self, msg):
        if msg.is_error_frame or msg.is_remote_frame or (msg.is_extended_id == False):
            return

        try:
            self.ecu.notify(msg.arbitration_id, msg.data, msg.timestamp)
        except Exception as e:
            # Exceptions in any callbaks should not affect CAN processing
            logger.error(str(e))
