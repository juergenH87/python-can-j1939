from .parameter_group_number import ParameterGroupNumber
from .message_id import MessageId
import logging
import time
import numpy as np

logger = logging.getLogger(__name__)

class J1939_22:
    class TpControlType:
        RTS        = 0   # Destination Specific Request_To_Send
        CTS        = 1   # Destination Specific Clear_To_Send
        EOM_STATUS = 2   # Destination Specific or Global Destination End_of_Message Status
        EOM_ACK    = 3   # Destination Specific End_of_Message Acknowledge
        BAM        = 4   # Global Destination Broadcast Announce Message
        ABORT      = 15  # Destination Specific Connection Abort

    class Adt: # assurance data type
        NO_ADT = 0              # no assurance Data
        MS_CS = 1               # Manufacturer specific cybersecurity assurance data
        MS_FS = 2               # Manufacturer specific functional safety assurance
        MS_COMBINED_CS_FS = 3   # Manufacturer specific combined cybersecurity followed by functional safety assurance

    class ConnectionAbortReason:
        BUSY = 1        # Already  in  one  or  more  connection  managed  sessions  and  cannot  support another
        RESOURCES = 2   # System  resources  were  needed  for  another  task  so  this  connection  managed session was terminated
        TIMEOUT = 3     # A timeout occured
        # 4..250 Reserved by SAE
        CTS_WHILE_DT = 4  # according AUTOSAR: CTS messages received when data transfer is in progress
        # 251..255 Per J1939/71 definitions - but there are none?

    class DataLength:
        TP = 60
        MULTI_PG = 60

    class Timeout:
        """Timeouts according SAE J1939/22"""
        Tr = 0.200 # Maximum Response Time
        Th = 0.500 # Maximum time, for responder, between transmits of consecutive CTS messages during hold
        T1 = 0.750 # Transport Segment Interval
        T2 = 1.250 # Maximum time, for responder, to receive a DT segment after a CTS - Originator Failure
        T3 = 1.250 # Maximum time, for originator, to receive a CTS after last DT segment - Responder Failure
        T4 = 1.050 # Maximum time, for originator, to receive the next CTS messages since the previous “hold” CTS to hold a connection open
        T5 = 3.000 # Maximum time, for originator, to receive EOMA after sending EOMS

    class SendBufferState:
        WAITING_CTS = 0        # waiting for CTS
        SENDING_RTS_CTS = 1    # sending rts/cts packages
        SENDING_BAM = 2        # sending broadcast packages
        SENDING_EOM_STATUS = 3 # sending end of message
        WAITING_EOM_ACK = 4    # waiting for end of message acknowledge
        EOM_ACK_RECEIVED = 5   # eom acknowledge received successfully

    class Acknowledgement:
        ACK = 0
        NACK = 1
        AccessDenied = 2
        CannotRespond = 3

    def __init__(self, send_message, job_thread_wakeup, notify_subscribers, max_cmdt_packets, minimum_tp_rts_cts_dt_interval, minimum_tp_bam_dt_interval, ecu_is_message_acceptable):
        # Receive buffers
        self._rcv_buffer = {}
        # Send buffers
        self._snd_buffer = {}
        # Multi-PG Send buffers
        self._multi_pg_snd_buffer = {}

        # List of ControllerApplication
        self._cas = []

        self._LUT_FD_DLC = []
        for i in range(9):  self._LUT_FD_DLC.append(i)
        for _ in range(4):  self._LUT_FD_DLC.append(12)
        for _ in range(4):  self._LUT_FD_DLC.append(16)
        for _ in range(4):  self._LUT_FD_DLC.append(20)
        for _ in range(4):  self._LUT_FD_DLC.append(24)
        for _ in range(8):  self._LUT_FD_DLC.append(32)
        for _ in range(16): self._LUT_FD_DLC.append(48)
        for _ in range(16): self._LUT_FD_DLC.append(64)

        # minimum time between two tp rts/cts dt frames, not necessary for standard conforming applications,
        # (they would use RTS/CTS flow control), but helps to talk to others without patching the library
        self._minimum_tp_rts_cts_dt_interval = minimum_tp_rts_cts_dt_interval

        # minimum time between two tp bam dt frames, inital value is 10ms
        # specified time range in j1939-22: 10-200ms
        if minimum_tp_bam_dt_interval == None:
            self._minimum_tp_bam_dt_interval = 0.010

        # Up to 4 concurrent BAM sessions per originator address are allowed
        self.__bam_session_list = [True] * 4

        # Up to 8 concurrent RTS/CTS sessions per originator and responder address pair are allowed.
        self.__rts_cts_session_list = [True] * 8

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

    def _buffer_hash(self, session_num, src_address, dest_address):
        """Calcluates a hash value for the given address pair

        :param src_address:
            The Source-Address the connection should bound to.
        :param dest_address:
            The Destination-Address the connection should bound to.

        :return:
            The calculated hash value.

        :rtype: int
        """
        return (((session_num & 0xF) << 16) | (src_address & 0xFF) << 8) | (dest_address & 0xFF)

    def _buffer_unhash(self, hash):
        """Calcluates session-number, source-address and destination-address for the given hash value

        :param hash:
            The hash to be unhased

        :return:
            The session-number, source-address and destination-address
        """
        return ((hash >> 16) & 0xFF), ((hash >> 8) & 0xFF), (hash & 0xFF)

    def __get_bam_session(self):
        for idx, i in enumerate(self.__bam_session_list):
            if i == True:
                self.__bam_session_list[idx] = False
                return idx
        return None

    def __put_bam_session(self, session):
        self.__bam_session_list[session] = True

    def __get_rts_cts_session(self):
        for idx, i in enumerate(self.__rts_cts_session_list):
            if i == True:
                self.__rts_cts_session_list[idx] = False
                return idx
        return None

    def __put_rts_cts_session(self, session):
        self.__rts_cts_session_list[session] = True

    def send_pgn(self, data_page, pdu_format, pdu_specific, priority, src_address, data, time_limit=0, tos = 2, trailer_format = 0):
        pgn = ParameterGroupNumber(data_page, pdu_format, pdu_specific)
        data_length = len(data)

        if data_length <= self.DataLength.TP:
            if (tos != 2) or (trailer_format != 0):
                print('currently "SAE J1939 with no assurance data" trailer format supported only')

            if pgn.is_pdu1_format:
                cpgn = pgn.value & 0xFFF00
                dst_address = pdu_specific
            else:
                cpgn = pgn.value
                dst_address = ParameterGroupNumber.Address.GLOBAL

            # create header dict
            cpg = {'priority': (priority & 0x7), 'tos': (tos & 0x7), 'tf': (trailer_format & 0x7), 'cpgn': (cpgn & 0x3FFFF), 'data_length': data_length, 'data': data.copy()}

            # send immediately
            if time_limit == 0:
                self.__send_multi_pg([cpg], src_address, dst_address)
            else:
                session = 0
                deadline = time.time() + time_limit
                while True:
                    hash = self._buffer_hash(session, src_address, dst_address)
                    if hash not in self._multi_pg_snd_buffer:
                        self._multi_pg_snd_buffer[hash] = {'deadline': deadline, 'cpg': [cpg], 'fill_level': 4 + data_length}
                        break
                    elif (self._multi_pg_snd_buffer[hash]['fill_level'] <= (self.DataLength.TP - data_length)):
                        # update fill level
                        self._multi_pg_snd_buffer[hash]['fill_level'] += 4 + data_length
                        # update deadline
                        if self._multi_pg_snd_buffer[hash]['deadline'] > deadline:
                            self._multi_pg_snd_buffer[hash]['deadline'] = deadline
                        # append c-pg
                        self._multi_pg_snd_buffer[hash]['cpg'].append(cpg)
                        break
                    else:
                        # trigger sending
                        self._multi_pg_snd_buffer[hash]['deadline'] = time.time()
                        self.__job_thread_wakeup()
                        # get next buffer
                        session += 1
        else:
            # if the PF is between 0 and 239, the message is destination dependent when pdu_specific != 255
            # if the PF is between 240 and 255, the message can only be broadcast
            if (pdu_specific == ParameterGroupNumber.Address.GLOBAL) or ParameterGroupNumber(0, pdu_format, pdu_specific).is_pdu2_format:
                dest_address = ParameterGroupNumber.Address.GLOBAL
                session_num = self.__get_bam_session()
                if session_num == None:
                    print('bam session not available')
                    return False
            else:
                dest_address = pdu_specific
                session_num = self.__get_rts_cts_session()
                if session_num == None:
                    print('rts/cts session not available')
                    return False

            # init sequence
            buffer_hash = self._buffer_hash(session_num, src_address, dest_address)

            message_size = data_length
            num_segments = int(message_size / self.DataLength.TP ) + ((message_size % self.DataLength.TP ) != 0)

            # set default priority
            if priority == None: priority = 7

            # get chunks from data
            full_tp_size_packages = int(data_length/self.DataLength.TP)
            arr = np.array(data)
            list_of_arr = np.split(arr, [full_tp_size_packages*self.DataLength.TP])
            arr = np.reshape(list_of_arr[0], (-1,self.DataLength.TP))
            data_list = arr.tolist()
            if len(list_of_arr) > 1:
                data_list.append(list_of_arr[1].tolist())

            # if the PF is between 240 and 255, the message can only be broadcast
            if dest_address == ParameterGroupNumber.Address.GLOBAL:

                # send BAM
                self.__send_tp_bam(priority, src_address, session_num, pgn.value, message_size, num_segments)

                # init new buffer for this connection
                self._snd_buffer[buffer_hash] = {
                        'pgn': pgn.value,
                        'priority': priority,
                        'session': session_num,
                        'message_size': message_size,
                        'num_segments': num_segments,
                        'data': data_list,
                        'state': self.SendBufferState.SENDING_BAM,
                        'deadline': time.time() + self._minimum_tp_bam_dt_interval,
                        'src_address' : src_address,
                        'dest_address' : ParameterGroupNumber.Address.GLOBAL,
                        'next_packet_to_send' : 0,
                    }
            else:
                # send RTS/CTS
                pgn.pdu_specific = 0  # this is 0 for peer-to-peer transfer
                # init new buffer for this connection
                self._snd_buffer[buffer_hash] = {
                        'pgn': pgn.value,
                        'priority': priority,
                        'session': session_num,
                        'message_size': message_size,
                        'num_segments': num_segments,
                        'data': data_list,
                        'state': self.SendBufferState.WAITING_CTS,
                        'deadline': time.time() + self.Timeout.T3,
                        'src_address' : src_address,
                        'dest_address' : pdu_specific,
                        'next_packet_to_send' : 0,
                        'next_wait_on_cts': 0,
                    }
                self.__send_tp_rts(priority, src_address, pdu_specific, session_num, pgn.value, message_size, num_segments, min(self._max_cmdt_packets, num_segments))

            self.__job_thread_wakeup()

        return True

    def __send_multi_pg(self, cpg_list, src_address, dst_address):
        # deadline reached
        priority = 7
        data = []
        for cpg in cpg_list:
            priority = min(cpg['priority'], priority)
            data.append( (cpg['tos'] << 5) | (cpg['tf'] << 2) | ((cpg['cpgn'] >> 16) & 0x3) )
            data.append( ((cpg['cpgn'] >> 8) & 0xFF) )
            data.append( (cpg['cpgn'] & 0xFF) )
            data.append( cpg['data_length'] )
            data.extend( cpg['data'])

        # padding
        next_valid_fd_length = self._LUT_FD_DLC[len(data)]
        if next_valid_fd_length < 0:
            next_valid_fd_length = 0

        # padding with service header 0
        padding_cnt = 0
        while len(data)<next_valid_fd_length:
            if padding_cnt < 3:
                data.append(0)
                padding_cnt += 1
            else:
                data.append(0xAA)

        mid = MessageId(priority=priority,
                        parameter_group_number=ParameterGroupNumber.PGN.FEFF_MULTI_PG | (dst_address & 0xFF),
                        source_address=src_address)
        self.__send_message(mid.can_id, data, fd_format=True)


    def async_job_thread(self, now):

        next_wakeup = now + 5.0 # wakeup in 5 seconds

        # check receive buffers for timeout
        # using 'list(x)' to prevent 'RuntimeError: dictionary changed size during iteration'
        for bufid in list(self._rcv_buffer):
            buf = self._rcv_buffer[bufid]
            if buf['deadline'] != 0:
                if buf['deadline'] > now:
                    if next_wakeup > buf['deadline']:
                        next_wakeup = buf['deadline']
                else:
                    # deadline reached
                    logger.info('Deadline reached for rcv_buffer src 0x%02X dst 0x%02X', buf['src_address'], buf['dest_address'] )
                    if buf['dest_address'] != ParameterGroupNumber.Address.GLOBAL:
                        self.__send_tp_abort(buf['dest_address'], buf['src_address'], buf['session'], self.ConnectionAbortReason.TIMEOUT, buf['pgn'])
                        del self._rcv_buffer[bufid]
                        self.__put_rts_cts_session(buf['session'])
                    else:
                        del self._rcv_buffer[bufid]
                        self.__put_bam_session(buf['session'])
                    # TODO: should we notify our CAs about the cancelled transfer?

        # check multi-pg send buffers for timeout
        # using 'list(x)' to prevent 'RuntimeError: dictionary changed size during iteration'
        for bufid in list(self._multi_pg_snd_buffer):
            buf = self._multi_pg_snd_buffer[bufid]
            if buf['deadline'] > now:
                if next_wakeup > buf['deadline']:
                    next_wakeup = buf['deadline']
            else:
                # deadline reached
                session_num, src_address, dst_address = self._buffer_unhash(bufid)

                self.__send_multi_pg(buf['cpg'], src_address, dst_address)

                del self._multi_pg_snd_buffer[bufid]


        # check send buffers
        # using 'list(x)' to prevent 'RuntimeError: dictionary changed size during iteration'
        for bufid in list(self._snd_buffer):
            buf = self._snd_buffer[bufid]
            if buf['deadline'] != 0:
                if buf['deadline'] > now:
                    if next_wakeup > buf['deadline']:
                        next_wakeup = buf['deadline']
                else:
                    # deadline reached
                    if buf['state'] == self.SendBufferState.WAITING_CTS:
                        logger.info('Deadline WAITING_CTS reached for snd_buffer src 0x%02X dst 0x%02X', buf['src_address'], buf['dest_address'] )
                        self.__send_tp_abort(buf['src_address'], buf['dest_address'], buf['session'], self.ConnectionAbortReason.TIMEOUT, buf['pgn'])
                        del self._snd_buffer[bufid]
                        self.__put_rts_cts_session(buf['session'])
                        # TODO: should we notify our CAs about the cancelled transfer?

                    elif buf['state'] == self.SendBufferState.SENDING_RTS_CTS:
                        while buf['next_packet_to_send'] < buf['num_segments']:
                            package = buf['next_packet_to_send']
                            self.__send_tp_dt(buf['src_address'], buf['dest_address'], buf['session'], package+1, buf['data'][package])

                            buf['next_packet_to_send'] += 1
                            # send end of message status
                            if (package+1) == buf['num_segments']:
                                self.__send_tp_eom_status(buf['src_address'], buf['dest_address'], buf['session'], buf['message_size'], buf['num_segments'], buf['pgn'])
                                buf['deadline'] = time.time() + self.Timeout.T5
                                buf['state'] = self.SendBufferState.WAITING_EOM_ACK
                                break
                            elif package == buf['next_wait_on_cts']:
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

                    elif buf['state'] == self.SendBufferState.WAITING_EOM_ACK:
                        # TODO: should we inform the application about the eom ack timeout?
                        del self._snd_buffer[bufid]
                        self.__put_rts_cts_session(buf['session'])

                    elif buf['state'] == self.SendBufferState.EOM_ACK_RECEIVED:
                        # TODO: should we inform the application about the successful transmission?
                        del self._snd_buffer[bufid]
                        self.__put_rts_cts_session(buf['session'])

                    elif buf['state'] == self.SendBufferState.SENDING_BAM:
                        # send next broadcast message...
                        package = buf['next_packet_to_send']
                        self.__send_tp_dt(buf['src_address'], buf['dest_address'], buf['session'], package+1, buf['data'][package])
                        buf['next_packet_to_send'] += 1

                        if buf['next_packet_to_send'] < buf['num_segments']:
                            buf['deadline'] = time.time() + self._minimum_tp_bam_dt_interval
                            # recalc next wakeup
                            if next_wakeup > buf['deadline']:
                                next_wakeup = buf['deadline']
                        else:
                            buf['state'] = self.SendBufferState.SENDING_EOM_STATUS
                            # recalc next wakeup
                            buf['deadline'] = time.time() + self._minimum_tp_bam_dt_interval
                            if next_wakeup > buf['deadline']:
                                next_wakeup = buf['deadline']

                    elif buf['state'] == self.SendBufferState.SENDING_EOM_STATUS:
                        # done
                        self.__send_tp_eom_status(buf['src_address'], buf['dest_address'],
                                                  buf['session'],
                                                  buf['message_size'], buf['num_segments'], buf['pgn'])
                        del self._snd_buffer[bufid]
                        self.__put_bam_session(buf['session'])
                    else:
                        logger.critical('unknown SendBufferState %d', buf['state'])
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

        # check minimum tp-cm length
        if len(data) < 12:
            logger.info('tp-cm with incorrect dlc received, id', mid )
            return

        src_address = mid.source_address
        control_byte  = data[0] & 0xF
        session_num   = (data[0] >> 4) & 0xF
        message_size  = (data[1]  & 0xFF) | ((data[2]  & 0xFF) << 8) | ((data[3] & 0xFF)  << 16)
        segment_num   = (data[4]  & 0xFF) | ((data[5]  & 0xFF) << 8) | ((data[6] & 0xFF)  << 16)
        pgn           = (data[9] & 0xFF)  | ((data[10] & 0xFF) << 8) | ((data[11] & 0xFF) << 16)

        if control_byte == self.TpControlType.RTS:
            buffer_hash   = self._buffer_hash(session_num, src_address, dest_address)
            num_segments = data[7] # Maximum number of segments that can be sent in response to one CTS.

            if buffer_hash in self._rcv_buffer:
                # according SAE J1939-22 we have to send an ABORT if an active
                # transmission is already established
                self.__send_tp_abort(dest_address, src_address, session_num, self.ConnectionAbortReason.BUSY, pgn)
                self.__put_rts_cts_session(session_num)
                return

            # limit max number segments
            num_segments = min(num_segments, segment_num)

            # open new buffer for this connection
            self._rcv_buffer[buffer_hash] = {
                    'pgn': pgn,
                    'session': session_num,
                    'message_size': message_size, # total message size, number of bytes
                    'num_segments': segment_num,  # total number of segments
                    'next_packet': 1,
                    'next_cts_border': min(self._max_cmdt_packets, num_segments),
                    'num_segments_max_rec': min(self._max_cmdt_packets, num_segments),
                    'data': [],
                    'deadline': time.time() + self.Timeout.T2,
                    'src_address' : src_address,
                    'dest_address' : dest_address,
                }
            self.__send_tp_cts(dest_address, src_address, session_num, self._rcv_buffer[buffer_hash]['num_segments_max_rec'], 1, pgn)
            self.__job_thread_wakeup()

        elif control_byte == self.TpControlType.CTS:
            buffer_hash   = self._buffer_hash(session_num, dest_address, src_address)
            num_segments = data[7] # Maximum number of segments that can be sent
            if buffer_hash not in self._snd_buffer:
                self.__send_tp_abort(dest_address, src_address, session_num, self.ConnectionAbortReason.RESOURCES, pgn)
                self.__put_rts_cts_session(session_num)
                return
            if num_segments == 0:
                # SAE J1939/22
                # receiver requests a pause
                self._snd_buffer[buffer_hash]['deadline'] = time.time() + self.Timeout.Th
                self.__job_thread_wakeup()
                return

            num_segments_all = self._snd_buffer[buffer_hash]['num_segments']
            self._snd_buffer[buffer_hash]['next_packet_to_send'] = segment_num - 1
            segments_to_be_sent = num_segments_all - self._snd_buffer[buffer_hash]['next_packet_to_send']
            if num_segments > num_segments_all:
                logger.debug("CTS: Allowed more packets %d than complete transmission %d", num_segments, num_segments_all)
                num_segments = num_segments_all
            if num_segments > self._max_cmdt_packets:
                logger.debug("CTS: Allowed more packets %d than transmitters max-cmdt-number %d", num_segments, self._max_cmdt_packets)
                num_segments = self._max_cmdt_packets
            if num_segments > segments_to_be_sent:
                logger.debug("CTS: Allowed more packets %d than needed to complete transmission %d", num_segments, segments_to_be_sent)
                num_segments = segments_to_be_sent

            self._snd_buffer[buffer_hash]['next_wait_on_cts'] = self._snd_buffer[buffer_hash]['next_packet_to_send'] + num_segments - 1

            self._snd_buffer[buffer_hash]['state'] = self.SendBufferState.SENDING_RTS_CTS
            self._snd_buffer[buffer_hash]['deadline'] = time.time() # wake up immediately
            self.__job_thread_wakeup()

        elif control_byte == self.TpControlType.EOM_STATUS:
            buffer_hash = self._buffer_hash(session_num, src_address, dest_address)
            if buffer_hash not in self._rcv_buffer:
                self.__put_rts_cts_session(session_num)
                return
            pgn = self._rcv_buffer[buffer_hash]['pgn']
            if (self._rcv_buffer[buffer_hash]['message_size'] == message_size) and (self._rcv_buffer[buffer_hash]['num_segments'] == segment_num):
                self.__notify_subscribers(mid.priority, pgn, src_address, dest_address, timestamp, self._rcv_buffer[buffer_hash]['data'])
                if dest_address != ParameterGroupNumber.Address.GLOBAL:
                    self.__send_tp_eom_ack(dest_address, src_address, session_num, message_size, segment_num, pgn)
            else:
                self.__send_tp_abort(dest_address, src_address, session_num, self.ConnectionAbortReason.RESOURCES, pgn)
            del self._rcv_buffer[buffer_hash]
            self.__put_rts_cts_session(session_num)

        elif control_byte == self.TpControlType.EOM_ACK:
            buffer_hash   = self._buffer_hash(session_num, dest_address, src_address)
            if buffer_hash not in self._snd_buffer:
                self.__send_tp_abort(dest_address, src_address, session_num, self.ConnectionAbortReason.RESOURCES, pgn)
                self.__put_rts_cts_session(session_num)
                return
            # TODO: should we inform the application about the successful transmission?
            self._snd_buffer[buffer_hash]['state'] = self.SendBufferState.EOM_ACK_RECEIVED
            self._snd_buffer[buffer_hash]['deadline'] = time.time() # wake up immediately
            self.__job_thread_wakeup()

        # BAM FD.TP.CM received
        elif control_byte == self.TpControlType.BAM:
            buffer_hash   = self._buffer_hash(session_num, src_address, dest_address)
            if buffer_hash in self._rcv_buffer:
                # buffer already in use
                logger.info('bam receive buffer already in use 0x%x', buffer_hash )
                del self._rcv_buffer[buffer_hash]
                self.__put_bam_session(self._rcv_buffer['session'])
                return

            # init new buffer for this connection
            self._rcv_buffer[buffer_hash] = {
                    'pgn': pgn,
                    'session': session_num,
                    'message_size': message_size, # Total message size, number of bytes
                    'num_segments': segment_num,  # Total number of segments
                    'next_packet': 1,
                    'data': [],
                    'deadline': time.time() + self.Timeout.T1,
                    'src_address' : src_address,
                    'dest_address' : dest_address,
                }
            self.__job_thread_wakeup()

        elif control_byte == self.TpControlType.ABORT:
            # if abort received before transmission established -> cancel transmission
            buffer_hash = self._buffer_hash(session_num, dest_address, src_address)
            if buffer_hash in self._snd_buffer and self._snd_buffer[buffer_hash]['state'] == self.SendBufferState.WAITING_CTS:
                del self._snd_buffer[buffer_hash] # cancel transmission
            # TODO: any more abort responses?
        else:
            raise RuntimeError('Received TP.CM with unknown control_byte %d', control_byte)

    def _process_tp_dt(self, mid, dest_address, data, timestamp):

        # check minimum tp-dt length
        if len(data) <= 4:
            logger.info('tp-dt with incorrect dlc received, id', mid )
            return

        src_address = mid.source_address
        dtfi        =  data[0] & 0xF # Data Transfer Format Indicator
        session_num = (data[0] >> 4) & 0xF
        segment_num = (data[1] & 0xFF) | ((data[2]  & 0xFF) << 8) | ((data[3] & 0xFF)  << 16)

        if segment_num == 0:
            logger.critical('segment number of 0 is not valid.')
            return

        buffer_hash = self._buffer_hash(session_num, src_address, dest_address)
        if buffer_hash not in self._rcv_buffer:
            logger.critical('buffer error process dt 0x%x', buffer_hash)
            return

        if self._rcv_buffer[buffer_hash]['next_packet'] != segment_num:
            logger.critical('packet error. required: '+ str(self._rcv_buffer[buffer_hash]['next_packet']) + ' received: ' + str(segment_num) )
            return

        # get data
        self._rcv_buffer[buffer_hash]['data'].extend(data[4:])

        self._rcv_buffer[buffer_hash]['next_packet'] = segment_num + 1

        # message is complete with sending an acknowledge
        if len(self._rcv_buffer[buffer_hash]['data']) >= self._rcv_buffer[buffer_hash]['message_size']:
            logger.info('finished RCV of PGN {} with size {}'.format(self._rcv_buffer[buffer_hash]['pgn'], self._rcv_buffer[buffer_hash]['message_size']))
            # shorten data to message_size
            self._rcv_buffer[buffer_hash]['data'] = self._rcv_buffer[buffer_hash]['data'][:self._rcv_buffer[buffer_hash]['message_size']]
            # finished reassembly
            if dest_address != ParameterGroupNumber.Address.GLOBAL:
                # set deadlin for waiting on eom status
                self._rcv_buffer[buffer_hash]['deadline'] = time.time() + self.Timeout.T1
            self.__job_thread_wakeup()
            return

        # send clear to send
        if (dest_address != ParameterGroupNumber.Address.GLOBAL) and (segment_num >= self._rcv_buffer[buffer_hash]['next_cts_border']):
            # send cts
            number_of_packets_that_can_be_sent = min( self._rcv_buffer[buffer_hash]['num_segments_max_rec'], self._rcv_buffer[buffer_hash]['num_segments'] - self._rcv_buffer[buffer_hash]['next_cts_border'] )
            next_packet_to_be_sent = self._rcv_buffer[buffer_hash]['next_cts_border'] + 1
            self.__send_tp_cts(dest_address, src_address, session_num, number_of_packets_that_can_be_sent, next_packet_to_be_sent, self._rcv_buffer[buffer_hash]['pgn'])

            # calculate next packet number at which a CTS is to be sent
            self._rcv_buffer[buffer_hash]['next_cts_border'] = min(self._rcv_buffer[buffer_hash]['next_cts_border'] + self._rcv_buffer[buffer_hash]['num_segments_max_rec'],
                                                               self._rcv_buffer[buffer_hash]['num_segments'])

            self._rcv_buffer[buffer_hash]['deadline'] = time.time() + self.Timeout.T2
            self.__job_thread_wakeup()
            return

        self._rcv_buffer[buffer_hash]['deadline'] = time.time() + self.Timeout.T1
        #self.__job_thread_wakeup()

    def _process_multi_pg(self, mid : MessageId, dest_address, data, timestamp):
        # currently "SAE J1939 with no assurance data" trailer format supported only
        src_address = mid.source_address

        while True:
            if len(data) <= 4:
                break
            tos            = (data[0] >> 5) & 0x7
            # padding service
            if tos == 0:
                break

            trailer_format = (data[0] >> 2) & 0x7
            cpgn           = ((data[0] & 0x3) << 16) | (data[1] << 8)  | data[2]
            payload_length = (data[3] & 0xFF)
            if (tos == 2) and (trailer_format == 0):
                # SAE J1939 with no assurance data
                self.__notify_subscribers(mid.priority, cpgn, src_address, dest_address, timestamp, data[4:(4+payload_length)].copy())
            else:
                # TODO
                print('other tos/tf formats currently not supported')

            # trim data
            data = data[(4+payload_length):]

    def __send_tp_abort(self, src_address, dest_address, session_num, reason, pgn_value):
        self.__send_tp_cm(src_address, dest_address, self.TpControlType.ABORT, session_num, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF, reason, pgn_value)

    def __send_tp_rts(self, priority, src_address, dest_address, session_num, pgn_value, message_size, num_segments, max_cmdt_packets, adt=Adt.NO_ADT):
        self.__send_tp_cm(src_address, dest_address, self.TpControlType.RTS, session_num, message_size, num_segments, max_cmdt_packets, adt, pgn_value, priority)

    def __send_tp_cts(self, src_address, dest_address, session_num, num_segments_that_can_be_sent, next_packet, pgn_value):
        request_code = 0
        self.__send_tp_cm(src_address, dest_address, self.TpControlType.CTS, session_num, 0xFFFFFF, next_packet, num_segments_that_can_be_sent, request_code, pgn_value)

    def __send_tp_eom_status(self, src_address, dest_address, session_num, message_size, num_segments, pgn_value, size_of_assurance_data=0, adt=Adt.NO_ADT):
        self.__send_tp_cm(src_address, dest_address, self.TpControlType.EOM_STATUS, session_num, message_size, num_segments, size_of_assurance_data, adt, pgn_value)

    def __send_tp_eom_ack(self, src_address, dest_address, session_num, message_size, num_segments, pgn_value):
        self.__send_tp_cm(src_address, dest_address, self.TpControlType.EOM_ACK, session_num, message_size, num_segments, 0xFF, 0xFF, pgn_value)

    def __send_tp_bam(self, priority, src_address, session_num, pgn_value, message_size, num_segments):
        self.__send_tp_cm(src_address, ParameterGroupNumber.Address.GLOBAL, self.TpControlType.BAM, session_num, message_size, num_segments, 0xFF , 0, pgn_value, priority)

    def __send_tp_cm(self,  src_address, dest_address,
                            TpControlType : TpControlType, session_num, message_size,
                            num_segments, # total number of segments or next segment number to be sent
                            byte_7, # maximum number of segments or num of segments that can be sent or assurance data Size
                            byte_8, # assurance data type or request code or teason code:
                            pgn,
                            priority=7):

        pgn_tp_cm = ParameterGroupNumber(0, (ParameterGroupNumber.PGN.FD_TP_CM>>8) & 0xFF, dest_address)
        mid = MessageId(priority=priority, parameter_group_number=pgn_tp_cm.value, source_address=src_address)

        data = [0] * 12
        data[0]  = ( (TpControlType & 0xF) | ((session_num & 0xF) << 4))
        data[1]  = (  message_size & 0xFF )
        data[2]  = ( (message_size >> 8)  & 0xFF )
        data[3]  = ( (message_size >> 16) & 0xFF )
        data[4]  = (  num_segments & 0xFF )
        data[5]  = ( (num_segments >> 8) & 0xFF )
        data[6]  = ( (num_segments >> 16) & 0xFF )
        data[7]  = (  byte_7 & 0xFF )
        data[8]  = (  byte_8 & 0xFF )
        data[9]  = (  pgn & 0xFF )
        data[10] = ( (pgn >> 8) & 0xFF )
        data[11] = ( (pgn >> 16) & 0xFF )
        # 13 up to 64 Assurance Data of full message calculated using AD Type. Total length = Size in byte 8.
        self.__send_message(mid.can_id, data, fd_format=True)

    def __send_tp_dt(self, src_address, dest_address, session_num, segment_num, data, Dtfi=0):
        pgn = ParameterGroupNumber(0, (ParameterGroupNumber.PGN.FD_TP_DT>>8) & 0xFF, dest_address)
        mid = MessageId(priority=7, parameter_group_number=pgn.value, source_address=src_address)

        data.insert(0, (Dtfi & 0xF) | ((session_num & 0xF) << 4))
        data.insert(1,  segment_num & 0xFF)
        data.insert(2, (segment_num >> 8) & 0xFF)
        data.insert(3, (segment_num >> 16) & 0xFF)

        next_valid_fd_length = 0
        if len(data)>=(self.DataLength.TP+4):
            data = data[:(self.DataLength.TP+4)]
        else:
            # padding
            next_valid_fd_length = self._LUT_FD_DLC[len(data)]
            if next_valid_fd_length < 0: next_valid_fd_length = 0

            while len(data)<next_valid_fd_length:
                data.append(255)

        self.__send_message(mid.can_id, data, fd_format=True)


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

        if pgn_value == ParameterGroupNumber.PGN.FEFF_MULTI_PG:
            self._process_multi_pg(mid, dest_address, data, timestamp)
        elif pgn_value == ParameterGroupNumber.PGN.ADDRESSCLAIM:
            for ca in self._cas:
                ca._process_addressclaim(mid, data, timestamp)
        elif pgn_value == ParameterGroupNumber.PGN.REQUEST:
            for ca in self._cas:
                if ca.message_acceptable(dest_address):
                    ca._process_request(mid, dest_address, data, timestamp)
        elif pgn_value == ParameterGroupNumber.PGN.FD_TP_CM:
            self._process_tp_cm(mid, dest_address, data, timestamp)
        elif pgn_value == ParameterGroupNumber.PGN.FD_TP_DT:
            self._process_tp_dt(mid, dest_address, data, timestamp)
        elif pgn_value == ParameterGroupNumber.PGN.TP_CM:
            logger.info('j1939-21 transport protocol cm not allowed in j1939-22 network')
        elif pgn_value == ParameterGroupNumber.PGN.DATATRANSFER:
            logger.info('j1939-21 transport protocol dt not allowed in j1939-22 network')
        elif pgn.is_pdu2_format:
            # direct broadcast
            self.__notify_subscribers(mid.priority, pgn.value, mid.source_address, ParameterGroupNumber.Address.GLOBAL, timestamp, data)
        else:
            self.__notify_subscribers(mid.priority, pgn_value, mid.source_address, dest_address, timestamp, data)

