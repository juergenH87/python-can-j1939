"""ISO 11783-3 Extended Transport Protocol (ETP).

ETP transports destination-specific messages from 1786 bytes up to
117 440 505 bytes. The state machine mirrors the J1939-21 TP RTS/CTS flow but
adds a Data Packet Offset (DPO) message between each CTS and its DT burst so
that the 1-byte DT sequence number can index a 24-bit packet count.

There is no broadcast variant: ETP.CM and ETP.DT sent to the global address
are ignored.

Every entry point (``start_send``, ``async_job_thread``, ``process_cm``,
``process_dt``, ``drop_sessions``) must be called with the owning data link
layer's lock held, since they are driven from both the CAN notifier thread
and the ECU job thread.

See ISO 11783-3 (2018 / 2025 draft) section 6.11.
"""
import logging
import time

from .parameter_group_number import ParameterGroupNumber
from .message_id import MessageId

logger = logging.getLogger(__name__)


class ISO11783_ETP:
    # Lower bound: TP covers up to 1785 bytes (ISO 11783-3 6.10)
    MIN_MESSAGE_SIZE = 1786
    # Upper bound: (2^24 - 1) packets * 7 bytes (ISO 11783-3 6.11.3)
    MAX_MESSAGE_SIZE = 117440505
    MAX_PACKETS = 0xFFFFFF

    # Packets requested per CTS when receiving, unless configured otherwise
    DEFAULT_MAX_CTS_PACKETS = 16

    # PF assignments per ISO 11783-3 6.11.5 / 6.11.6
    PF_CM = 200  # PGN 51200 (0xC800)
    PF_DT = 199  # PGN 50944 (0xC700)

    # Connection management and data transfer are sent at priority 7
    PRIORITY = 7

    # A connection management message that fails to send is tried again
    CONTROL_ATTEMPTS = 3
    CONTROL_RETRY_INTERVAL = 0.010

    class ControlByte:
        """Control bytes for ETP.CM messages."""
        RTS = 20
        CTS = 21
        DPO = 22
        EOM_ACK = 23
        ABORT = 255

    class AbortReason:
        """ETP.Conn_Abort reasons (ISO 11783-3 Table 14)."""
        BUSY = 1
        RESOURCES = 2
        TIMEOUT = 3
        CTS_WHILE_DT = 4
        MAX_RETRANSMIT = 5
        UNEXPECTED_DT = 6
        BAD_SEQUENCE = 7
        DUPLICATE_SEQUENCE = 8
        UNEXPECTED_DPO = 9
        UNEXPECTED_DPO_PGN = 10
        DPO_NUM_PACKETS_GT_CTS = 11
        BAD_DPO_OFFSET = 12
        UNEXPECTED_CTS_PGN = 14
        CTS_REQUESTED_PACKETS_EXCEEDS_SIZE = 15
        ANY_OTHER_REASON = 250

    class Timeout:
        """Timing per ISO 11783-3 6.11.4.1 (inherited from TP)."""
        Th = 0.500
        T1 = 0.750
        T2 = 1.250
        T3 = 1.250
        T4 = 1.050

    class SendState:
        WAITING_CTS = 0
        SENDING_DPO = 1
        SENDING_IN_CTS = 2
        TRANSMISSION_FINISHED = 3

    def __init__(self, send_message, job_thread_wakeup, notify_subscribers,
                 max_cmdt_packets, minimum_dt_interval, tp_receiving=None):
        """
        :param max_cmdt_packets:
            Packets to request per CTS when receiving (1..255).
        :param minimum_dt_interval:
            Minimum time between two ETP.DT messages when sending, or None.
        :param tp_receiving:
            Callable ``(src_address, dest_address) -> bool`` telling whether a
            TP connection is open on that pair, so an ETP RTS can be refused
            while one is.
        """
        self.__send_message = send_message
        self.__job_thread_wakeup = job_thread_wakeup
        self.__notify_subscribers = notify_subscribers
        self._max_cmdt_packets = max_cmdt_packets
        self._minimum_dt_interval = minimum_dt_interval
        self._tp_receiving = tp_receiving or (lambda src_address, dest_address: False)

        self._snd_buffer = {}
        self._rcv_buffer = {}

    @staticmethod
    def _buffer_hash(src_address, dest_address):
        return ((src_address & 0xFF) << 8) | (dest_address & 0xFF)

    # --- Public API ---------------------------------------------------------

    def has_send_session(self, src_address, dest_address):
        """Whether an ETP send from src_address to dest_address is open."""
        return self._buffer_hash(src_address, dest_address) in self._snd_buffer

    def has_receive_session(self, src_address, dest_address):
        """Whether an ETP receive from src_address to dest_address is open."""
        return self._buffer_hash(src_address, dest_address) in self._rcv_buffer

    def start_send(self, src_address, dest_address, priority, pgn_value, data):
        """Start an ETP send session.

        ``data`` may be any sequence of byte values (list, bytes, bytearray).
        ``priority`` is accepted for symmetry with TP; ETP.CM and ETP.DT are
        always sent at priority 7.

        Returns True if the session was opened (RTS already sent). Returns
        False if the size is out of range or an ETP session is already active
        for this (src, dest) pair.
        """
        message_size = len(data)
        if message_size < self.MIN_MESSAGE_SIZE:
            return False
        if message_size > self.MAX_MESSAGE_SIZE:
            logger.error("Message size %d exceeds ETP limit (%d)",
                         message_size, self.MAX_MESSAGE_SIZE)
            return False
        buffer_hash = self._buffer_hash(src_address, dest_address)
        if buffer_hash in self._snd_buffer:
            return False
        # PGN field in CM messages carries PS=0 for peer-to-peer transfer
        cm_pgn = pgn_value & 0x3FF00
        num_packages = (message_size + 6) // 7
        self._snd_buffer[buffer_hash] = {
            'pgn': cm_pgn,
            'message_size': message_size,
            'num_packages': num_packages,
            'data': bytes(data),
            'state': self.SendState.WAITING_CTS,
            'deadline': time.time() + self.Timeout.T3,
            'src_address': src_address,
            'dest_address': dest_address,
            'next_packet_to_send': 0,
            'next_wait_on_cts': 0,
            'data_packet_offset': 0,
        }
        self.__send_rts(src_address, dest_address, cm_pgn, message_size)
        return True

    def drop_sessions(self, address):
        """Forget every session in which ``address`` is the local end, without
        sending anything: the address is no longer ours to send from."""
        for bufid in list(self._snd_buffer):
            if self._snd_buffer[bufid]['src_address'] == address:
                del self._snd_buffer[bufid]
        for bufid in list(self._rcv_buffer):
            if self._rcv_buffer[bufid]['dest_address'] == address:
                del self._rcv_buffer[bufid]

    def async_job_thread(self, now):
        """Drive ETP send-buffer states and check receive-buffer timeouts.

        Returns the time the caller's job thread should wake next.
        """
        next_wakeup = now + 5.0

        for bufid in list(self._rcv_buffer):
            buf = self._rcv_buffer[bufid]
            if buf['deadline'] > now:
                next_wakeup = min(next_wakeup, buf['deadline'])
                continue
            logger.info("ETP receive timeout src 0x%02X dst 0x%02X",
                        buf['src_address'], buf['dest_address'])
            self.__send_abort(buf['dest_address'], buf['src_address'],
                              self.AbortReason.TIMEOUT, buf['pgn'])
            del self._rcv_buffer[bufid]

        for bufid in list(self._snd_buffer):
            buf = self._snd_buffer[bufid]
            if buf['deadline'] > now:
                next_wakeup = min(next_wakeup, buf['deadline'])
                continue
            state = buf['state']
            if state == self.SendState.WAITING_CTS:
                logger.info("ETP WAITING_CTS timeout src 0x%02X dst 0x%02X",
                            buf['src_address'], buf['dest_address'])
                self.__send_abort(buf['src_address'], buf['dest_address'],
                                  self.AbortReason.TIMEOUT, buf['pgn'])
                del self._snd_buffer[bufid]
            elif state == self.SendState.SENDING_DPO:
                # Sequence numbers restart at 1 for each new DPO group
                # (ISO 11783-3 6.11.5.5).
                burst_count = buf['next_wait_on_cts'] - buf['next_packet_to_send'] + 1
                self.__send_dpo(buf['src_address'], buf['dest_address'],
                                burst_count, buf['data_packet_offset'], buf['pgn'])
                buf['state'] = self.SendState.SENDING_IN_CTS
                buf['burst_seq'] = 0
                buf['deadline'] = time.time()
                next_wakeup = min(next_wakeup, buf['deadline'])
            elif state == self.SendState.SENDING_IN_CTS:
                self._send_burst(buf)
                if buf['state'] == self.SendState.TRANSMISSION_FINISHED:
                    del self._snd_buffer[bufid]
                else:
                    next_wakeup = min(next_wakeup, buf['deadline'])
            elif state == self.SendState.TRANSMISSION_FINISHED:
                del self._snd_buffer[bufid]
            else:
                logger.critical("ETP unknown send state %d", state)
                del self._snd_buffer[bufid]

        return next_wakeup

    def _send_burst(self, buf):
        while (buf['state'] == self.SendState.SENDING_IN_CTS
               and buf['next_packet_to_send'] <= buf['next_wait_on_cts']):
            package = buf['next_packet_to_send']
            chunk = buf['data'][package * 7:package * 7 + 7]
            buf['burst_seq'] += 1
            payload = [buf['burst_seq']] + list(chunk) + [0xFF] * (7 - len(chunk))
            buf['next_packet_to_send'] += 1
            should_break = False
            if package == buf['next_wait_on_cts']:
                # Wait for the next CTS, or for EOM_ACK after the last packet
                buf['state'] = self.SendState.WAITING_CTS
                buf['deadline'] = time.time() + self.Timeout.T3
                should_break = True
            elif self._minimum_dt_interval is not None:
                buf['deadline'] = time.time() + self._minimum_dt_interval
                should_break = True
            self.__send_dt(buf['src_address'], buf['dest_address'], payload)
            if should_break:
                break

    def process_cm(self, mid, dest_address, data, timestamp):
        """Process an incoming ETP.CM message."""
        if dest_address == ParameterGroupNumber.Address.GLOBAL or len(data) < 8:
            return
        control_byte = data[0]
        pgn_value = data[5] | (data[6] << 8) | (data[7] << 16)
        src_address = mid.source_address

        if control_byte == self.ControlByte.RTS:
            self._handle_rts(src_address, dest_address, data, pgn_value)
        elif control_byte == self.ControlByte.CTS:
            self._handle_cts(src_address, dest_address, data, pgn_value)
        elif control_byte == self.ControlByte.DPO:
            self._handle_dpo(src_address, dest_address, data, pgn_value)
        elif control_byte == self.ControlByte.EOM_ACK:
            self._handle_eom_ack(mid, src_address, dest_address, timestamp, data, pgn_value)
        elif control_byte == self.ControlByte.ABORT:
            self._handle_abort(src_address, dest_address, pgn_value)
        else:
            logger.warning("ETP.CM unknown control_byte %d", control_byte)

    def process_dt(self, mid, dest_address, data, timestamp):
        """Process an incoming ETP.DT message."""
        if dest_address == ParameterGroupNumber.Address.GLOBAL or len(data) < 1:
            return
        sequence_number = data[0]
        src_address = mid.source_address
        buffer_hash = self._buffer_hash(src_address, dest_address)
        rcv = self._rcv_buffer.get(buffer_hash)
        if rcv is None:
            return

        if rcv['expected_dpo']:
            self._abort_receive(buffer_hash, self.AbortReason.UNEXPECTED_DT)
            return
        if 1 <= sequence_number <= rcv['burst_received']:
            self._abort_receive(buffer_hash, self.AbortReason.DUPLICATE_SEQUENCE)
            return
        if sequence_number != rcv['burst_received'] + 1 or sequence_number > rcv['dpo_packets']:
            self._abort_receive(buffer_hash, self.AbortReason.BAD_SEQUENCE)
            return
        rcv['burst_received'] = sequence_number

        # Absolute packet number = DPO + sequence; data lives at (abs-1)*7.
        absolute_packet = rcv['cts_dpo'] + sequence_number
        write_offset = (absolute_packet - 1) * 7
        chunk = bytes(data[1:8])
        rcv['data'][write_offset:write_offset + len(chunk)] = chunk

        if absolute_packet == rcv['num_packages']:
            del self._rcv_buffer[buffer_hash]
            self.__send_eom_ack(dest_address, src_address, rcv['message_size'], rcv['pgn'])
            self.__notify_subscribers(mid.priority, rcv['pgn'], src_address, dest_address,
                                      timestamp, list(rcv['data'][:rcv['message_size']]))
            self.__job_thread_wakeup()
            return

        if sequence_number == rcv['dpo_packets']:
            self._clear_to_send(rcv, absolute_packet + 1)
            return

        rcv['deadline'] = time.time() + self.Timeout.T1
        self.__job_thread_wakeup()

    # --- ETP.CM handlers ----------------------------------------------------

    def _handle_rts(self, src_address, dest_address, data, pgn_value):
        message_size = data[1] | (data[2] << 8) | (data[3] << 16) | (data[4] << 24)
        buffer_hash = self._buffer_hash(src_address, dest_address)
        existing = self._rcv_buffer.get(buffer_hash)
        if existing is not None and existing['pgn'] != pgn_value:
            # Another PGN is in progress on this pair; it continues.
            self.__send_abort(dest_address, src_address, self.AbortReason.BUSY, pgn_value)
            return
        if existing is None and self._tp_receiving(src_address, dest_address):
            self.__send_abort(dest_address, src_address, self.AbortReason.BUSY, pgn_value)
            return
        if message_size < self.MIN_MESSAGE_SIZE or message_size > self.MAX_MESSAGE_SIZE:
            self._rcv_buffer.pop(buffer_hash, None)
            self.__send_abort(dest_address, src_address,
                              self.AbortReason.ANY_OTHER_REASON, pgn_value)
            return
        if existing is not None:
            # The most recent RTS for the same PGN replaces the open connection.
            logger.info("ETP RTS restarts the connection src 0x%02X dst 0x%02X",
                        src_address, dest_address)
        num_packages = (message_size + 6) // 7
        rcv = {
            'pgn': pgn_value,
            'message_size': message_size,
            'num_packages': num_packages,
            'data': bytearray(num_packages * 7),
            'deadline': 0,
            'src_address': src_address,
            'dest_address': dest_address,
            'cts_packets': 0,
            'cts_dpo': 0,
            'expected_dpo': True,
            'dpo_packets': 0,
            'burst_received': 0,
        }
        self._rcv_buffer[buffer_hash] = rcv
        self._clear_to_send(rcv, 1)

    def _handle_cts(self, src_address, dest_address, data, pgn_value):
        num_packets = data[1]
        next_packet_number = data[2] | (data[3] << 8) | (data[4] << 16)
        buffer_hash = self._buffer_hash(dest_address, src_address)
        buf = self._snd_buffer.get(buffer_hash)
        if buf is None or buf['state'] == self.SendState.TRANSMISSION_FINISHED:
            self.__send_abort(dest_address, src_address,
                              self.AbortReason.RESOURCES, pgn_value)
            return
        if buf['pgn'] != pgn_value:
            self._abort_send(buffer_hash, self.AbortReason.UNEXPECTED_CTS_PGN, pgn_value)
            return
        if num_packets == 0:
            # Hold the connection open (ISO 11783-3 6.11.5.4); the receiver
            # repeats the hold every Th, and the originator waits up to T4.
            buf['deadline'] = time.time() + self.Timeout.T4
            self.__job_thread_wakeup()
            return
        if next_packet_number < 1 or next_packet_number > buf['num_packages']:
            self._abort_send(buffer_hash, self.AbortReason.CTS_REQUESTED_PACKETS_EXCEEDS_SIZE,
                             pgn_value)
            return
        # A CTS while a burst is still going out replaces the window: the
        # receiver is asking for packets again from next_packet_number.
        remaining = buf['num_packages'] - (next_packet_number - 1)
        if num_packets > remaining:
            num_packets = remaining
        buf['next_packet_to_send'] = next_packet_number - 1
        buf['next_wait_on_cts'] = buf['next_packet_to_send'] + num_packets - 1
        buf['data_packet_offset'] = next_packet_number - 1
        buf['state'] = self.SendState.SENDING_DPO
        buf['deadline'] = time.time()
        self.__job_thread_wakeup()

    def _handle_dpo(self, src_address, dest_address, data, pgn_value):
        num_packets = data[1]
        data_packet_offset = data[2] | (data[3] << 8) | (data[4] << 16)
        buffer_hash = self._buffer_hash(src_address, dest_address)
        rcv = self._rcv_buffer.get(buffer_hash)
        if rcv is None:
            self.__send_abort(dest_address, src_address,
                              self.AbortReason.UNEXPECTED_DPO, pgn_value)
            return
        if rcv['pgn'] != pgn_value:
            self._abort_receive(buffer_hash, self.AbortReason.UNEXPECTED_DPO_PGN)
            return
        if not rcv['expected_dpo']:
            self._abort_receive(buffer_hash, self.AbortReason.UNEXPECTED_DPO)
            return
        if num_packets == 0 or num_packets > rcv['cts_packets']:
            self._abort_receive(buffer_hash, self.AbortReason.DPO_NUM_PACKETS_GT_CTS)
            return
        if data_packet_offset != rcv['cts_dpo']:
            self._abort_receive(buffer_hash, self.AbortReason.BAD_DPO_OFFSET)
            return
        rcv['dpo_packets'] = num_packets
        rcv['burst_received'] = 0
        rcv['expected_dpo'] = False
        rcv['deadline'] = time.time() + self.Timeout.T1
        self.__job_thread_wakeup()

    def _handle_eom_ack(self, mid, src_address, dest_address, timestamp, data, pgn_value):
        buffer_hash = self._buffer_hash(dest_address, src_address)
        buf = self._snd_buffer.get(buffer_hash)
        if buf is None:
            self.__send_abort(dest_address, src_address,
                              self.AbortReason.RESOURCES, pgn_value)
            return
        if buf['pgn'] != pgn_value or buf['state'] == self.SendState.TRANSMISSION_FINISHED:
            return
        message_size = data[1] | (data[2] << 8) | (data[3] << 16) | (data[4] << 24)
        if (buf['state'] != self.SendState.WAITING_CTS
                or buf['next_packet_to_send'] < buf['num_packages']
                or message_size != buf['message_size']):
            logger.warning("ETP EOM_ACK before the whole message was sent src 0x%02X dst 0x%02X",
                           dest_address, src_address)
            self._abort_send(buffer_hash, self.AbortReason.ANY_OTHER_REASON, pgn_value)
            return
        # As with TP, subscribers learn of the completed send from the EOM_ACK
        self.__notify_subscribers(mid.priority, pgn_value, src_address,
                                  dest_address, timestamp, data)
        buf['state'] = self.SendState.TRANSMISSION_FINISHED
        buf['deadline'] = time.time()
        self.__job_thread_wakeup()

    def _handle_abort(self, src_address, dest_address, pgn_value):
        # An abort names its connection by PGN; it ends only that connection,
        # whichever direction it runs in.
        snd_hash = self._buffer_hash(dest_address, src_address)
        rcv_hash = self._buffer_hash(src_address, dest_address)
        buf = self._snd_buffer.get(snd_hash)
        if buf is not None and buf['pgn'] == pgn_value:
            logger.info("ETP send aborted by the receiver src 0x%02X dst 0x%02X",
                        dest_address, src_address)
            buf['state'] = self.SendState.TRANSMISSION_FINISHED
            buf['deadline'] = time.time()
        rcv = self._rcv_buffer.get(rcv_hash)
        if rcv is not None and rcv['pgn'] == pgn_value:
            logger.info("ETP receive aborted by the sender src 0x%02X dst 0x%02X",
                        src_address, dest_address)
            del self._rcv_buffer[rcv_hash]
        self.__job_thread_wakeup()

    # --- Session helpers ----------------------------------------------------

    def _clear_to_send(self, rcv, next_packet):
        count = min(self._max_cmdt_packets, rcv['num_packages'] - next_packet + 1, 0xFF)
        rcv['cts_packets'] = count
        rcv['cts_dpo'] = next_packet - 1
        rcv['dpo_packets'] = 0
        rcv['burst_received'] = 0
        rcv['expected_dpo'] = True
        rcv['deadline'] = time.time() + self.Timeout.T2
        self.__send_cts(rcv['dest_address'], rcv['src_address'], count, next_packet, rcv['pgn'])
        self.__job_thread_wakeup()

    def _abort_receive(self, buffer_hash, reason):
        rcv = self._rcv_buffer.pop(buffer_hash)
        self.__send_abort(rcv['dest_address'], rcv['src_address'], reason, rcv['pgn'])
        self.__job_thread_wakeup()

    def _abort_send(self, buffer_hash, reason, pgn_value):
        buf = self._snd_buffer.pop(buffer_hash)
        self.__send_abort(buf['src_address'], buf['dest_address'], reason, pgn_value)
        self.__job_thread_wakeup()

    # --- ETP.CM and ETP.DT senders -----------------------------------------
    # Multi-byte fields are little-endian; PGN field carries PS=0.

    def __send_cm(self, src_address, dest_address, data):
        pgn = ParameterGroupNumber(0, self.PF_CM, dest_address)
        mid = MessageId(priority=self.PRIORITY, parameter_group_number=pgn.value,
                        source_address=src_address)
        for attempt in range(self.CONTROL_ATTEMPTS):
            try:
                self.__send_message(mid.can_id, True, data)
                return
            except Exception:
                if attempt == self.CONTROL_ATTEMPTS - 1:
                    raise
                time.sleep(self.CONTROL_RETRY_INTERVAL)

    def __send_rts(self, src_address, dest_address, pgn_value, message_size):
        self.__send_cm(src_address, dest_address, [
            self.ControlByte.RTS,
            message_size & 0xFF, (message_size >> 8) & 0xFF,
            (message_size >> 16) & 0xFF, (message_size >> 24) & 0xFF,
            pgn_value & 0xFF, (pgn_value >> 8) & 0xFF, (pgn_value >> 16) & 0xFF,
        ])

    def __send_cts(self, src_address, dest_address, num_packets, next_packet, pgn_value):
        self.__send_cm(src_address, dest_address, [
            self.ControlByte.CTS,
            num_packets & 0xFF,
            next_packet & 0xFF, (next_packet >> 8) & 0xFF, (next_packet >> 16) & 0xFF,
            pgn_value & 0xFF, (pgn_value >> 8) & 0xFF, (pgn_value >> 16) & 0xFF,
        ])

    def __send_dpo(self, src_address, dest_address, num_packets, offset, pgn_value):
        self.__send_cm(src_address, dest_address, [
            self.ControlByte.DPO,
            num_packets & 0xFF,
            offset & 0xFF, (offset >> 8) & 0xFF, (offset >> 16) & 0xFF,
            pgn_value & 0xFF, (pgn_value >> 8) & 0xFF, (pgn_value >> 16) & 0xFF,
        ])

    def __send_eom_ack(self, src_address, dest_address, message_size, pgn_value):
        self.__send_cm(src_address, dest_address, [
            self.ControlByte.EOM_ACK,
            message_size & 0xFF, (message_size >> 8) & 0xFF,
            (message_size >> 16) & 0xFF, (message_size >> 24) & 0xFF,
            pgn_value & 0xFF, (pgn_value >> 8) & 0xFF, (pgn_value >> 16) & 0xFF,
        ])

    def __send_abort(self, src_address, dest_address, reason, pgn_value):
        self.__send_cm(src_address, dest_address, [
            self.ControlByte.ABORT,
            reason, 0xFF, 0xFF, 0xFF,
            pgn_value & 0xFF, (pgn_value >> 8) & 0xFF, (pgn_value >> 16) & 0xFF,
        ])

    def __send_dt(self, src_address, dest_address, payload):
        pgn = ParameterGroupNumber(0, self.PF_DT, dest_address)
        mid = MessageId(priority=self.PRIORITY, parameter_group_number=pgn.value,
                        source_address=src_address)
        self.__send_message(mid.can_id, True, payload)
