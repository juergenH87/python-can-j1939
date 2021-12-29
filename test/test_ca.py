
# for standalone-test
import sys
sys.path.append(".")

import unittest
import time
import threading

try:
    # Python27
    import Queue as queue
except ImportError:
    # Python35
    import queue

import j1939

class TestCA(unittest.TestCase):
    # TODO: should we change the async_can_feeder to use the can backend with
    #       bustype 'virtual' instead of injecting our messages directly?

    class MsgType(object):
        CANRX = 0
        CANTX = 1
        PDU = 2

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
        while self.can_messages and self.can_messages[0][0] == TestCA.MsgType.CANRX:
            message = self.can_messages.pop(0)
            self.message_queue.put(message)

    def _send_message(self, can_id, data):
        """Will be used instead of the usual ecu.send_message method.

        Checks the message sent and generates the apropriate answer.
        The data is fed from self.can_messages. 
        """
        expected_data = self.can_messages.pop(0)
        self.assertEqual(expected_data[0], TestCA.MsgType.CANTX, "No transmission was expected")
        self.assertEqual(can_id, expected_data[1])
        self.assertSequenceEqual(data, expected_data[2])
        self._inject_messages_into_ecu()

    def setUp(self):
        """Called before each test methode.
        Method called to prepare the test fixture. This is called immediately 
        before calling the test method; other than AssertionError or SkipTest, 
        any exception raised by this method will be considered an error rather 
        than a test failure. The default implementation does nothing.
        """
        self.STOP_THREAD = object()

        self.message_queue = queue.Queue()
        self.message_thread = threading.Thread(target=self._async_can_feeder)
        self.message_thread.start()
        # redirect the send_message from the can bus to our simulation
        self.ecu = j1939.ElectronicControlUnit(send_message=self._send_message)

    def tearDown(self):
        """Called after each test methode.
        Method called immediately after the test method has been called and 
        the result recorded. This is called even if the test method raised an 
        exception, so the implementation in subclasses may need to be 
        particularly careful about checking internal state. Any exception, 
        other than AssertionError or SkipTest, raised by this method will be 
        considered an additional error rather than a test failure (thus 
        increasing the total number of reported errors). This method will only 
        be called if the setUp() succeeds, regardless of the outcome of the 
        test method. The default implementation does nothing.
        """
        self.ecu.stop()
        self.message_queue.put(self.STOP_THREAD)
        self.message_thread.join()

    def test_addr_claim_fixed(self):
        """Test CA Address claim on the bus with fixed address
        This test runs a "Single Address Capable" claim procedure with a fixed
        address of 128.
        """
        self.can_messages = [
            (TestCA.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),    # Address Claimed
        ]

        name = j1939.Name(
            arbitrary_address_capable=0, 
            industry_group=j1939.Name.IndustryGroup.Industrial,
            vehicle_system_instance=2,
            vehicle_system=127,
            function=201,
            function_instance=16,
            ecu_instance=2,
            manufacturer_code=666,
            identity_number=1234567
            )
        # create new CA on the bus with given NAME and ADDRESS
        new_ca = self.ecu.add_ca(name=name, device_address=128)
        # by starting the CA it announces the given ADDRESS on the bus
        new_ca.start()
        
        # wait until all messages are processed asynchronously
        while len(self.can_messages)>0:
            time.sleep(0.500)
        # wait for final processing    
        time.sleep(0.500)

        self.assertEqual(new_ca.state, j1939.ControllerApplication.State.NORMAL)        
        
    def test_addr_claim_fixed_veto_lose(self):
        """Test CA Address claim on the bus with fixed address and a veto counterpart
        This test runs a "Single Address Capable" claim procedure with a fixed
        address of 128. A counterpart on the bus declines the address claimed message
        with a veto and we lose our address.
        """
        self.can_messages = [
            (TestCA.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),    # Address Claimed
            (TestCA.MsgType.CANRX, 0x18EEFF80, [135, 214, 82, 83, 130, 111, 254, 82], 0.0),    # Veto from Counterpart with lower name
            (TestCA.MsgType.CANTX, 0x18EEFFFE, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),    # CANNOT CLAIM
        ]

        name = j1939.Name(
            arbitrary_address_capable=0, 
            industry_group=j1939.Name.IndustryGroup.Industrial,
            vehicle_system_instance=2,
            vehicle_system=127,
            function=201,
            function_instance=16,
            ecu_instance=2,
            manufacturer_code=666,
            identity_number=1234567
            )
        # create new CA on the bus with given NAME and ADDRESS
        new_ca = self.ecu.add_ca(name=name, device_address=128)
        # by starting the CA it announces the given ADDRESS on the bus
        new_ca.start()
        
        # wait until all messages are processed asynchronously
        while len(self.can_messages)>0:
            time.sleep(0.500)
        # wait for final processing    
        time.sleep(0.500)

        self.assertEqual(new_ca.state, j1939.ControllerApplication.State.CANNOT_CLAIM)        

    def test_addr_claim_fixed_veto_win(self):
        """Test CA Address claim on the bus with fixed address and a veto counterpart
        This test runs a "Single Address Capable" claim procedure with a fixed
        address of 128. A counterpart on the bus declines the address claimed message
        with a veto, but our name is less.
        """
        self.can_messages = [
            (TestCA.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),    # Address Claimed
            (TestCA.MsgType.CANRX, 0x18EEFF80, [135, 214, 82, 83, 130, 222, 254, 82], 0.0),    # Veto from Counterpart with higher name
            (TestCA.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),    # resend Address Claimed
        ]

        name = j1939.Name(
            arbitrary_address_capable=0, 
            industry_group=j1939.Name.IndustryGroup.Industrial,
            vehicle_system_instance=2,
            vehicle_system=127,
            function=201,
            function_instance=16,
            ecu_instance=2,
            manufacturer_code=666,
            identity_number=1234567
            )
        # create new CA on the bus with given NAME and ADDRESS
        new_ca = self.ecu.add_ca(name=name, device_address=128)
        # by starting the CA it announces the given ADDRESS on the bus
        new_ca.start()
        
        # wait until all messages are processed asynchronously
        while len(self.can_messages)>0:
            time.sleep(0.500)
        # wait for final processing    
        time.sleep(0.500)

        self.assertEqual(new_ca.state, j1939.ControllerApplication.State.NORMAL)        

    def test_addr_claim_arbitrary_veto_lose(self):
        """Test CA Address claim on the bus with arbitrary capability a veto counterpart
        This test runs a "Arbitrary Address Capable" claim procedure with an
        address of 128. A counterpart on the bus declines the address claimed message
        with a veto and we lose our address. Our device should claim the next address
        (129) automatically.
        """
        self.can_messages = [
            (TestCA.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 210], 0.0),    # Address Claimed 128
            (TestCA.MsgType.CANRX, 0x18EEFF80, [135, 214, 82, 83, 130, 111, 254, 82], 0.0),     # Veto from Counterpart with lower name
            (TestCA.MsgType.CANTX, 0x18EEFF81, [135, 214, 82, 83, 130, 201, 254, 210], 0.0),    # Address Claimed 129
        ]

        name = j1939.Name(
            arbitrary_address_capable=1, 
            industry_group=j1939.Name.IndustryGroup.Industrial,
            vehicle_system_instance=2,
            vehicle_system=127,
            function=201,
            function_instance=16,
            ecu_instance=2,
            manufacturer_code=666,
            identity_number=1234567
            )
        # create new CA on the bus with given NAME and ADDRESS
        new_ca = self.ecu.add_ca(name=name, device_address=128)
        # by starting the CA it announces the given ADDRESS on the bus
        new_ca.start()
        
        # wait until all messages are processed asynchronously
        while len(self.can_messages)>0:
            time.sleep(0.500)
        # wait for final processing    
        time.sleep(0.500)

        self.assertEqual(new_ca.state, j1939.ControllerApplication.State.NORMAL)        

if __name__ == '__main__':
    unittest.main()        
