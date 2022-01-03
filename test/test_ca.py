
# for standalone-test
import sys
sys.path.append(".")

import unittest
import time

import j1939
from feeder import Feeder

class TestCA(unittest.TestCase):
    def setUp(self):
        """Called before each test methode.
        Method called to prepare the test fixture. This is called immediately 
        before calling the test method; other than AssertionError or SkipTest, 
        any exception raised by this method will be considered an error rather 
        than a test failure. The default implementation does nothing.
        """
        self.feeder = Feeder()

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
        self.feeder.stop()

    def test_addr_claim_fixed(self):
        """Test CA Address claim on the bus with fixed address
        This test runs a "Single Address Capable" claim procedure with a fixed
        address of 128.
        """
        self.feeder.can_messages = [
            (Feeder.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),    # Address Claimed
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
        new_ca = self.feeder.ecu.add_ca(name=name, device_address=128)
        # by starting the CA it announces the given ADDRESS on the bus
        new_ca.start()
        
        # wait until all messages are processed asynchronously
        while len(self.feeder.can_messages)>0:
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
        self.feeder.can_messages = [
            (Feeder.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),    # Address Claimed
            (Feeder.MsgType.CANRX, 0x18EEFF80, [135, 214, 82, 83, 130, 111, 254, 82], 0.0),    # Veto from Counterpart with lower name
            (Feeder.MsgType.CANTX, 0x18EEFFFE, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),    # CANNOT CLAIM
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
        new_ca = self.feeder.ecu.add_ca(name=name, device_address=128)
        # by starting the CA it announces the given ADDRESS on the bus
        new_ca.start()
        
        # wait until all messages are processed asynchronously
        while len(self.feeder.can_messages)>0:
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
        self.feeder.can_messages = [
            (Feeder.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),    # Address Claimed
            (Feeder.MsgType.CANRX, 0x18EEFF80, [135, 214, 82, 83, 130, 222, 254, 82], 0.0),    # Veto from Counterpart with higher name
            (Feeder.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),    # resend Address Claimed
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
        new_ca = self.feeder.ecu.add_ca(name=name, device_address=128)
        # by starting the CA it announces the given ADDRESS on the bus
        new_ca.start()
        
        # wait until all messages are processed asynchronously
        while len(self.feeder.can_messages)>0:
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
        self.feeder.can_messages = [
            (Feeder.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 210], 0.0),    # Address Claimed 128
            (Feeder.MsgType.CANRX, 0x18EEFF80, [135, 214, 82, 83, 130, 111, 254, 82], 0.0),     # Veto from Counterpart with lower name
            (Feeder.MsgType.CANTX, 0x18EEFF81, [135, 214, 82, 83, 130, 201, 254, 210], 0.0),    # Address Claimed 129
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
        new_ca = self.feeder.ecu.add_ca(name=name, device_address=128)
        # by starting the CA it announces the given ADDRESS on the bus
        new_ca.start()
        
        # wait until all messages are processed asynchronously
        while len(self.feeder.can_messages)>0:
            time.sleep(0.500)
        # wait for final processing    
        time.sleep(0.500)

        self.assertEqual(new_ca.state, j1939.ControllerApplication.State.NORMAL)        

if __name__ == '__main__':
    unittest.main()        
