import queue

import time
import threading

import j1939


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

    def stop(self):
        self.ecu.stop()
        self.message_queue.put(self.STOP_THREAD)
        self.message_thread.join()
