import queue

import time
import threading

import j1939

class AcceptAllCA(j1939.ControllerApplication):
    """CA to accept all messages"""

    def __init__(self, name, device_address_preferred=None):
        # old fashion calling convention for compatibility with Python2
        j1939.ControllerApplication.__init__(self, name, device_address_preferred)

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

    def __init__(self):
        self.STOP_THREAD = object()

        self.message_queue = queue.Queue()
        self.message_thread = threading.Thread(target=self._async_can_feeder)
        self.message_thread.start()
        # redirect the send_message from the can bus to our simulation
        self.ecu = j1939.ElectronicControlUnit(send_message=self._send_message)

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

    def _send_message(self, can_id, data):
        """Will be used instead of the usual ecu.send_message method.

        Checks the message sent and generates the apropriate answer.
        The data is fed from self.can_messages.
        """
        expected_data = self.can_messages.pop(0)
        assert (
            expected_data[0] == Feeder.MsgType.CANTX,
            "No transmission was expected",
        )
        assert can_id == expected_data[1]
        assert data == expected_data[2]
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
        expected_data = self.pdus.pop(0)
        assert expected_data[0] == Feeder.MsgType.PDU
        assert pgn == expected_data[1]
        if isinstance(data, list):
            assert data == expected_data[2]
        else:
            assert data is None

    def accept_all_messages(self):
        # install a fake-CA to accept all messages
        ca = AcceptAllCA(None)
        self.ecu.add_ca(controller_application = ca)

    def receive(self):
        self.ecu.subscribe(self._on_message)
        self._inject_messages_into_ecu()
        # wait until all messages are processed asynchronously
        while len(self.pdus)>0:
            time.sleep(0.500)
        # wait for final processing    
        time.sleep(0.100)
        self.ecu.unsubscribe(self._on_message)

    def send(self, pdu, source, destination):
        self.ecu.subscribe(self._on_message)
    
        # sending from 240 to 155 with prio 6
        self.ecu.send_pgn(0, pdu[1]>>8, destination, 6, source, pdu[2])
        
        # wait until all messages are processed asynchronously
        while len(self.can_messages)>0:
            time.sleep(0.500)
        # wait for final processing    
        time.sleep(0.100)
        self.ecu.unsubscribe(self._on_message)

    def stop(self):
        self.ecu.stop()
        self.message_queue.put(self.STOP_THREAD)
        self.message_thread.join()
