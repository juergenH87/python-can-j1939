from .parameter_group_number import ParameterGroupNumber
from .message_id import MessageId
import logging
import time

logger = logging.getLogger(__name__)

class J1939_21:
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

    def __init__(self, send_message, job_thread_wakeup, notify_subscribers, max_cmdt_packets, minimum_tp_rts_cts_dt_interval, minimum_tp_bam_dt_interval, ecu_is_message_acceptable):
        # Receive buffers
        self._rcv_buffer = {}
        # Send buffers
        self._snd_buffer = {}

        # List of ControllerApplication
        self._cas = []

        # set minimum time between two tp-rts/cts messages
        self._minimum_tp_rts_cts_dt_interval = minimum_tp_rts_cts_dt_interval

        # set minimum time between two tp-bam messages
        if minimum_tp_bam_dt_interval == None:
            self._minimum_tp_bam_dt_interval = self.Timeout.Tb

        # number of packets that can be sent/received with CMDT (Connection Mode Data Transfer)
        self._max_cmdt_packets = max_cmdt_packets

        self.__job_thread_wakeup = job_thread_wakeup
        self.__send_message = send_message
        self.__notify_subscribers = notify_subscribers
        self.__ecu_is_message_acceptable = ecu_is_message_acceptable

    def add_ca(self, ca):
        self._cas.append(ca)

    def remove_ca(self, device_address):
        for ca in self._cas:
            if device_address == ca._device_address_preferred:
                self._cas.remove(ca)
                return True
        return False

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

    def send_pgn(self, data_page, pdu_format, pdu_specific, priority, src_address, data, time_limit=0):
        pgn = ParameterGroupNumber(data_page, pdu_format, pdu_specific)
        if len(data) <= 8:
            # send normal message
            mid = MessageId(priority=priority, parameter_group_number=pgn.value, source_address=src_address)
            self.__send_message(mid.can_id, data)
        else:
            # if the PF is between 0 and 239, the message is destination dependent when pdu_specific != 255
            # if the PF is between 240 and 255, the message can only be broadcast
            if (pdu_specific == ParameterGroupNumber.Address.GLOBAL) or ParameterGroupNumber(0, pdu_format, pdu_specific).is_pdu2_format:
                dest_address = ParameterGroupNumber.Address.GLOBAL
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
            if dest_address == ParameterGroupNumber.Address.GLOBAL:
                # send BAM
                self.__send_tp_bam(src_address, priority, pgn.value, message_size, num_packets)

                # init new buffer for this connection
                self._snd_buffer[buffer_hash] = {
                        "pgn": pgn.value,
                        "priority": priority,
                        "message_size": message_size,
                        "num_packages": num_packets,
                        "data": data,
                        "state": self.SendBufferState.SENDING_BM,
                        "deadline": time.time() + self._minimum_tp_bam_dt_interval,
                        'src_address' : src_address,
                        'dest_address' : ParameterGroupNumber.Address.GLOBAL,
                        'next_packet_to_send' : 0,
                    }
            else:
                # send RTS/CTS
                pgn.pdu_specific = 0  # this is 0 for peer-to-peer transfer
                # init new buffer for this connection
                self._snd_buffer[buffer_hash] = {
                        "pgn": pgn.value,
                        "priority": priority,
                        "message_size": message_size,
                        "num_packages": num_packets,
                        "data": data,
                        "state": self.SendBufferState.WAITING_CTS,
                        "deadline": time.time() + self.Timeout.T3,
                        'src_address' : src_address,
                        'dest_address' : pdu_specific,
                        'next_packet_to_send' : 0,
                        'next_wait_on_cts': 0,
                    }
                self.__send_tp_rts(src_address, pdu_specific, priority, pgn.value, message_size, num_packets, min(self._max_cmdt_packets, num_packets))

            self.__job_thread_wakeup()

        return True


    def async_job_thread(self, now):

        next_wakeup = now + 5.0 # wakeup in 5 seconds

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
                    if buf['dest_address'] != ParameterGroupNumber.Address.GLOBAL:
                        # TODO: should we handle retries?
                        self.__send_tp_abort(buf['dest_address'], buf['src_address'], self.ConnectionAbortReason.TIMEOUT, buf['pgn'])
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
                    if buf['state'] == self.SendBufferState.WAITING_CTS:
                        logger.info("Deadline WAITING_CTS reached for snd_buffer src 0x%02X dst 0x%02X", buf['src_address'], buf['dest_address'] )
                        self.__send_tp_abort(buf['src_address'], buf['dest_address'], self.ConnectionAbortReason.TIMEOUT, buf['pgn'])
                        # TODO: should we notify our CAs about the cancelled transfer?
                        del self._snd_buffer[bufid]
                    elif buf['state'] == self.SendBufferState.SENDING_IN_CTS:
                        while buf['next_packet_to_send'] < buf['num_packages']:
                            package = buf['next_packet_to_send']
                            offset = package * 7
                            data = buf['data'][offset:]
                            if len(data)>7:
                                data = data[:7]
                            else:
                                while len(data)<7:
                                    data.append(255)
                            data.insert(0, package+1)
                            self.__send_tp_dt(buf['src_address'], buf['dest_address'], data)

                            buf['next_packet_to_send'] += 1

                            # send end of message status
                            if package == buf['next_wait_on_cts']:
                                # wait on next cts
                                buf['state'] = self.SendBufferState.WAITING_CTS
                                buf['deadline'] = time.time() + self.Timeout.T3
                                break
                            elif self._minimum_tp_rts_cts_dt_interval != None:
                                buf['deadline'] = time.time() + self._minimum_tp_rts_cts_dt_interval
                                break

                        # recalc next wakeup
                        if next_wakeup > buf['deadline']:
                            next_wakeup = buf['deadline']

                    elif buf['state'] == self.SendBufferState.SENDING_BM:
                        # send next broadcast message...
                        offset = buf['next_packet_to_send'] * 7
                        data = buf['data'][offset:]
                        if len(data)>7:
                            data = data[:7]
                        else:
                            while len(data)<7:
                                data.append(255)
                        data.insert(0, buf['next_packet_to_send']+1)
                        self.__send_tp_dt(buf['src_address'], buf['dest_address'], data)
                        buf['next_packet_to_send'] += 1

                        if buf['next_packet_to_send'] < buf['num_packages']:
                            buf['deadline'] = time.time() + self._minimum_tp_bam_dt_interval
                            # recalc next wakeup
                            if next_wakeup > buf['deadline']:
                                next_wakeup = buf['deadline']
                        else:
                            # done
                            del self._snd_buffer[bufid]
                    else:
                        logger.critical("unknown SendBufferState %d", buf['state'])
                        del self._snd_buffer[bufid]

        return next_wakeup


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

        if control_byte == self.ConnectionMode.RTS:
            message_size = data[1] | (data[2] << 8)
            num_packages = data[3]
            max_num_packages = data[4] # Maximum number of segments that can be sent in response to one CTS.
            buffer_hash = self._buffer_hash(src_address, dest_address)
            if buffer_hash in self._rcv_buffer:
                # according SAE J1939-21 we have to send an ABORT if an active
                # transmission is already established
                self.__send_tp_abort(dest_address, src_address, self.ConnectionAbortReason.BUSY, pgn)
                return

            # limit max number segments
            max_num_packages = min(max_num_packages, num_packages)

            # open new buffer for this connection
            self._rcv_buffer[buffer_hash] = {
                    'pgn': pgn,
                    'message_size': message_size,
                    'num_packages': num_packages,
                    'next_packet': min(self._max_cmdt_packets, max_num_packages),
                    'max_cmdt_packages': self._max_cmdt_packets,
                    'num_packages_max_rec': min(self._max_cmdt_packets, max_num_packages),
                    'data': [],
                    'deadline': time.time() + self.Timeout.T2,
                    'src_address' : src_address,
                    'dest_address' : dest_address,
                }

            self.__send_tp_cts(dest_address, src_address, self._rcv_buffer[buffer_hash]['num_packages_max_rec'], 1, pgn)
            self.__job_thread_wakeup()
        elif control_byte == self.ConnectionMode.CTS:
            num_packages = data[1]
            next_package_number = data[2] - 1
            buffer_hash = self._buffer_hash(dest_address, src_address)
            if buffer_hash not in self._snd_buffer:
                self.__send_tp_abort(dest_address, src_address, self.ConnectionAbortReason.RESOURCES, pgn)
                return
            if num_packages == 0:
                # SAE J1939/21
                # receiver requests a pause
                self._snd_buffer[buffer_hash]['deadline'] = time.time() + self.Timeout.Th
                self.__job_thread_wakeup()
                return

            num_packages_all = self._snd_buffer[buffer_hash]["num_packages"]
            if num_packages > num_packages_all:
                logger.debug("CTS: Allowed more packets %d than complete transmission %d", num_packages, num_packages_all)
                num_packages = num_packages_all
            if next_package_number + num_packages > num_packages_all:
                logger.debug("CTS: Allowed more packets %d than needed to complete transmission %d", num_packages, num_packages_all - next_package_number)
                num_packages = num_packages_all - next_package_number

            self._snd_buffer[buffer_hash]['next_wait_on_cts'] = self._snd_buffer[buffer_hash]['next_packet_to_send'] + num_packages - 1

            self._snd_buffer[buffer_hash]['state'] = self.SendBufferState.SENDING_IN_CTS
            self._snd_buffer[buffer_hash]['deadline'] = time.time()
            self.__job_thread_wakeup()


        elif control_byte == self.ConnectionMode.EOM_ACK:
            buffer_hash = self._buffer_hash(dest_address, src_address)
            if buffer_hash not in self._snd_buffer:
                self.__send_tp_abort(dest_address, src_address, self.ConnectionAbortReason.RESOURCES, pgn)
                return
            # TODO: should we inform the application about the successful transmission?
            del self._snd_buffer[buffer_hash]
            self.__job_thread_wakeup()
        elif control_byte == self.ConnectionMode.BAM:
            message_size = data[1] | (data[2] << 8)
            num_packages = data[3]
            buffer_hash = self._buffer_hash(src_address, dest_address)
            if buffer_hash in self._rcv_buffer:
                # TODO: should we deliver the partly received message to our CAs?
                del self._rcv_buffer[buffer_hash]
                self.__job_thread_wakeup()

            # init new buffer for this connection
            self._rcv_buffer[buffer_hash] = {
                    "pgn": pgn,
                    "message_size": message_size,
                    "num_packages": num_packages,
                    "next_packet": 1,
                    "max_cmdt_packages": self._max_cmdt_packets,
                    "data": [],
                    "deadline": time.time() + self.Timeout.T1,
                    'src_address' : src_address,
                    'dest_address' : dest_address,
                }
            self.__job_thread_wakeup()
        elif control_byte == self.ConnectionMode.ABORT:
            # if abort received before transmission established -> cancel transmission
            buffer_hash = self._buffer_hash(dest_address, src_address)
            if buffer_hash in self._snd_buffer and self._snd_buffer[buffer_hash]['state'] == self.SendBufferState.WAITING_CTS:
                del self._snd_buffer[buffer_hash] # cancel transmission
            # TODO: any more abort responses?
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
            if dest_address != ParameterGroupNumber.Address.GLOBAL:
                self.__send_tp_eom_ack(dest_address, src_address, self._rcv_buffer[buffer_hash]['message_size'], self._rcv_buffer[buffer_hash]['num_packages'], self._rcv_buffer[buffer_hash]['pgn'])
            self.__notify_subscribers(mid.priority, self._rcv_buffer[buffer_hash]['pgn'], src_address, dest_address, timestamp, self._rcv_buffer[buffer_hash]['data'])
            del self._rcv_buffer[buffer_hash]
            self.__job_thread_wakeup()
            return

        # clear to send
        if (dest_address != ParameterGroupNumber.Address.GLOBAL) and (sequence_number >= self._rcv_buffer[buffer_hash]['next_packet']):

            # send cts
            number_of_packets_that_can_be_sent = min( self._rcv_buffer[buffer_hash]['num_packages_max_rec'], self._rcv_buffer[buffer_hash]['num_packages'] - self._rcv_buffer[buffer_hash]['next_packet'] )
            next_packet_to_be_sent = self._rcv_buffer[buffer_hash]['next_packet'] + 1
            self.__send_tp_cts(dest_address, src_address, number_of_packets_that_can_be_sent, next_packet_to_be_sent, self._rcv_buffer[buffer_hash]['pgn'])

            # calculate next packet number at which a CTS is to be sent
            self._rcv_buffer[buffer_hash]['next_packet'] = min(self._rcv_buffer[buffer_hash]['next_packet'] + self._rcv_buffer[buffer_hash]['num_packages_max_rec'],
                                                               self._rcv_buffer[buffer_hash]['num_packages'])

            self._rcv_buffer[buffer_hash]['deadline'] = time.time() + self.Timeout.T2
            self.__job_thread_wakeup()
            return

        self._rcv_buffer[buffer_hash]['deadline'] = time.time() + self.Timeout.T1
        self.__job_thread_wakeup()

    def __send_tp_dt(self, src_address, dest_address, data):
        pgn = ParameterGroupNumber(0, 235, dest_address)
        mid = MessageId(priority=7, parameter_group_number=pgn.value, source_address=src_address)
        self.__send_message(mid.can_id, data)

    def __send_tp_abort(self, src_address, dest_address, reason, pgn_value):
        pgn = ParameterGroupNumber(0, 236, dest_address)
        mid = MessageId(priority=7, parameter_group_number=pgn.value, source_address=src_address)
        data = [self.ConnectionMode.ABORT, reason, 0xFF, 0xFF, 0xFF, pgn_value & 0xFF, (pgn_value >> 8) & 0xFF, (pgn_value >> 16) & 0xFF]
        self.__send_message(mid.can_id, data)

    def __send_tp_cts(self, src_address, dest_address, num_packets, next_packet, pgn_value):
        pgn = ParameterGroupNumber(0, 236, dest_address)
        mid = MessageId(priority=7, parameter_group_number=pgn.value, source_address=src_address)
        data = [self.ConnectionMode.CTS, num_packets, next_packet, 0xFF, 0xFF, pgn_value & 0xFF, (pgn_value >> 8) & 0xFF, (pgn_value >> 16) & 0xFF]
        self.__send_message(mid.can_id, data)

    def __send_tp_eom_ack(self, src_address, dest_address, message_size, num_packets, pgn_value):
        pgn = ParameterGroupNumber(0, 236, dest_address)
        mid = MessageId(priority=7, parameter_group_number=pgn.value, source_address=src_address)
        data = [self.ConnectionMode.EOM_ACK, message_size & 0xFF, (message_size >> 8) & 0xFF, num_packets, 0xFF, pgn_value & 0xFF, (pgn_value >> 8) & 0xFF, (pgn_value >> 16) & 0xFF]
        self.__send_message(mid.can_id, data)

    def __send_tp_rts(self, src_address, dest_address, priority, pgn_value, message_size, num_packets, max_cmdt_packets):
        pgn = ParameterGroupNumber(0, 236, dest_address)
        mid = MessageId(priority=priority, parameter_group_number=pgn.value, source_address=src_address)
        data = [self.ConnectionMode.RTS, message_size & 0xFF, (message_size >> 8) & 0xFF, num_packets, max_cmdt_packets, pgn_value & 0xFF, (pgn_value >> 8) & 0xFF, (pgn_value >> 16) & 0xFF]
        self.__send_message(mid.can_id, data)

    def __send_acknowledgement(self, control_byte, group_function_value, address_acknowledged, pgn):
        data = [control_byte, group_function_value, 0xFF, 0xFF, address_acknowledged, (pgn & 0xFF), ((pgn >> 8) & 0xFF), ((pgn >> 16) & 0xFF)]
        mid = MessageId(priority=6, parameter_group_number=0x00E800, source_address=255)
        self.__send_message(mid.can_id, data)

    def __send_tp_bam(self, src_address, priority, pgn_value, message_size, num_packets):
        pgn = ParameterGroupNumber(0, 236, ParameterGroupNumber.Address.GLOBAL)
        mid = MessageId(priority=priority, parameter_group_number=pgn.value, source_address=src_address)
        data = [self.ConnectionMode.BAM, message_size & 0xFF, (message_size >> 8) & 0xFF, num_packets, 0xFF, pgn_value & 0xFF, (pgn_value >> 8) & 0xFF, (pgn_value >> 16) & 0xFF]
        self.__send_message(mid.can_id, data)

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

        mid = MessageId(can_id=can_id)
        pgn = ParameterGroupNumber()
        pgn.from_message_id(mid)

        if pgn.is_pdu2_format:
            # direct broadcast
            self.__notify_subscribers(mid.priority, pgn.value, mid.source_address, ParameterGroupNumber.Address.GLOBAL, timestamp, data)
            return

        # peer to peer
        # pdu_specific is destination Address
        pgn_value = pgn.value & 0x1FF00
        dest_address = pgn.pdu_specific # may be Address.GLOBAL

        # iterate all CAs to check if we have to handle this destination address
        if dest_address != ParameterGroupNumber.Address.GLOBAL:
            if not self.__ecu_is_message_acceptable(dest_address): # simple peer-to-peer reception without adding a controller-application
                reject = True
                for ca in self._cas:
                    if ca.message_acceptable(dest_address):
                        reject = False
                        break
                if reject == True:
                    return

        if pgn_value == ParameterGroupNumber.PGN.ADDRESSCLAIM:
            for ca in self._cas:
                ca._process_addressclaim(mid, data, timestamp)
        elif pgn_value == ParameterGroupNumber.PGN.REQUEST:
            for ca in self._cas:
                if ca.message_acceptable(dest_address):
                    ca._process_request(mid, dest_address, data, timestamp)
        elif pgn_value == ParameterGroupNumber.PGN.TP_CM:
            self._process_tp_cm(mid, dest_address, data, timestamp)
        elif pgn_value == ParameterGroupNumber.PGN.DATATRANSFER:
            self._process_tp_dt(mid, dest_address, data, timestamp)
        else:
            self.__notify_subscribers(mid.priority, pgn_value, mid.source_address, dest_address, timestamp, data)
            return

