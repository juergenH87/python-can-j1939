import logging
import queue
import threading
import time

import j1939
from j1939.message_id import MessageId
from j1939.parameter_group_number import ParameterGroupNumber

logger = logging.getLogger(__name__)


class AcceptAllCA(j1939.ControllerApplication):
    """CA to accept all messages"""

    def __init__(self, name, device_address_preferred, bypass_address_claim):
        # old fashion calling convention for compatibility with Python2
        j1939.ControllerApplication.__init__(self, name, device_address_preferred, bypass_address_claim)

    def message_acceptable(self, dest_address):
        """Indicates if this CA would accept a message
        (OVERLOADED FUNCTION)
        This function indicates the acceptance of this CA for the given dest_address.
        """
        return True


class Feeder:
    """
    Simulated/mocked CAN message feeder for tests.  Tests can use this class to specify
    expected rx and tx messages via Feeder.can_messages.  Overrides
    j1939.ElectronicControlUnit.send_message, checking that tx message data matches
    expected data, and then injecting the expected rx nessage into the ECU
    """

    class MsgType(object):
        CANRX = 0
        CANTX = 1
        PDU = 2

    def __init__(self, **ecu_kwargs):
        self.STOP_THREAD = object()
        # Assertions fail on the ECU's and the feeder's threads, where pytest
        # would only warn; they are recorded here and raised by check()
        self.failures = []

        self.message_queue = queue.Queue()
        self.message_thread = threading.Thread(target=self._async_can_feeder)
        self.message_thread.start()
        # redirect the send_message from the can bus to our simulation
        ecu_kwargs.setdefault('send_message', self._send_message)
        self.ecu = j1939.ElectronicControlUnit(**ecu_kwargs)

    def _async_can_feeder(self):
        """Asynchronous feeder"""
        while True:
            message = self.message_queue.get(block=True)
            if message is self.STOP_THREAD:
                break
            recv_time = message[3]
            if recv_time == 0.0:
                recv_time = time.time()
            self.ecu.notify(message[1], message[2], recv_time)

    def _inject_messages_into_ecu(self):
        while self.can_messages and self.can_messages[0][0] == Feeder.MsgType.CANRX:
            message = self.can_messages.pop(0)
            self.message_queue.put(message)

    def _send_message(self, can_id, extended_id, data, fd_format=False):
        """Will be used instead of the usual ecu.send_message method.

        Checks the message sent and generates the apropriate answer.
        The data is fed from self.can_messages.
        """
        logger.info(
            f'send message ID: {can_id:04x}, data:   {["{:02x}".format(val) for val in data]}'
        )
        with self._recording():
            assert self.can_messages, f'unexpected message ID {can_id:08x} data {list(data)}'
            expected_data = self.can_messages.pop(0)
            assert expected_data[0] == Feeder.MsgType.CANTX, f'sent ID {can_id:08x} data {list(data)} where {expected_data} was expected'
            assert can_id == expected_data[1], f'sent ID {can_id:08x} where {expected_data[1]:08x} was expected'
            assert list(data) == list(expected_data[2]), f'sent {list(data)} where {expected_data[2]} was expected'
        self._inject_messages_into_ecu()

    def _on_message(self, priority, pgn, sa, timestamp, data):
        """Feed incoming message to this testcase.

        :param int priority:
            Priority of the message
        :param int pgn:
            Parameter Group Number of the message
        :param sa:
            Source Address of the message
        :param timestamp:
            Timestamp of the message
        :param bytearray data:
            Data of the PDU
        """
        logger.info(
            f'received from sa {sa:02x} pgn {pgn:04x} data: {["{:02x}".format(val) for val in data]}'
        )
        with self._recording():
            assert self.pdus, f'unexpected PDU pgn {pgn:04x}'
            expected_data = self.pdus.pop(0)
            assert expected_data[0] == Feeder.MsgType.PDU
            assert pgn == expected_data[1], f'received PGN {pgn:04x} where {expected_data[1]:04x} was expected'
            assert list(data) == list(expected_data[2]), f'received {list(data)} where {expected_data[2]} was expected'

    class _Recording:
        def __init__(self, feeder):
            self.feeder = feeder

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            if exc_type is AssertionError:
                self.feeder.failures.append(exc)
                # nothing more will match: let the waiting test return
                self.feeder.can_messages = []
                self.feeder.pdus = []
                return True
            return False

    def _recording(self):
        return Feeder._Recording(self)

    def check(self):
        """Raise the first assertion that failed on a background thread."""
        if self.failures:
            raise self.failures[0]

    def pdus_from_messages(self):
        self.pdus = []
        for message in self.can_messages:
            if message[0] is Feeder.MsgType.CANRX:
                pgn = ParameterGroupNumber()
                pgn.from_message_id(MessageId(can_id=message[1]))
                self.pdus.append((Feeder.MsgType.PDU, pgn.value & 0xFF00, message[2]))

    def accept_all_messages(
        self, device_address_preferred=None, bypass_address_claim=False
    ):
        # install a fake-CA to accept all messages
        ca = AcceptAllCA(None, device_address_preferred, bypass_address_claim)

        self.ecu.add_ca(controller_application=ca)
        return ca

    def receive(self):
        self.ecu.subscribe(self._on_message)
        self._inject_messages_into_ecu()
        # wait until all messages are processed asynchronously
        while len(self.pdus) > 0:
            time.sleep(0.500)
        # wait for final processing
        time.sleep(0.100)
        self.ecu.unsubscribe(self._on_message)
        self.check()

    def send(self, pdu, source, destination):
        self.ecu.subscribe(self._on_message)
        self.ecu.send_pgn(0, pdu[1] >> 8, destination, 6, source, pdu[2])
        self.process_messages()

    def process_messages(self):
        # wait until all messages are processed asynchronously
        while len(self.can_messages) > 0:
            time.sleep(0.500)
        # wait for final processing
        time.sleep(0.100)
        self.ecu.unsubscribe(self._on_message)
        self.check()

    def stop(self):
        self.ecu.stop()
        self.message_queue.put(self.STOP_THREAD)
        self.message_thread.join()
