import time
# for standalone-test
import sys
sys.path.append(".")

import unittest

import j1939
from feeder import Feeder

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


class TestECU(unittest.TestCase):
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
        self.assertEqual(expected_data[0], Feeder.MsgType.PDU)
        self.assertEqual(pgn, expected_data[1])
        if isinstance(data, list):
            self.assertSequenceEqual(data, expected_data[2])
        else:
            self.assertIsNone(data)

    def setUp(self):
        """Called before each test methode.
        Method called to prepare the test fixture. This is called immediately 
        before calling the test method; other than AssertionError or SkipTest, 
        any exception raised by this method will be considered an error rather 
        than a test failure. The default implementation does nothing.
        """
        self.feeder = Feeder()
        # install a fake-CA to accept all messages
        ca = AcceptAllCA(None)
        self.feeder.ecu.add_ca(controller_application = ca)

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

    #def test_connect(self):
    #    self.feeder.ecu.connect(bustype="virtual", channel=1)
    #    self.feeder.ecu.disconnect()
    
    def test_broadcast_receive_short(self):
        """Test the receivement of a normal broadcast message

        For this test we receive the GFI1 (Fuel Information 1 (Gaseous)) PGN 65202 (FEB2).
        Its length is 8 Bytes. The contained values are bogous of cause.
        """
        
        self.feeder.can_messages = [
            (Feeder.MsgType.CANRX, 0x00FEB201, [1, 2, 3, 4, 5, 6, 7, 8], 0.0),   
        ]

        self.pdus = [
            (Feeder.MsgType.PDU, 65202, [1, 2, 3, 4, 5, 6, 7, 8]),
        ]

        self.feeder.ecu.subscribe(self._on_message)
        self.feeder._inject_messages_into_ecu()
        # wait until all messages are processed asynchronously
        while len(self.pdus)>0:
            time.sleep(0.500)
        # wait for final processing    
        time.sleep(0.100)
        self.feeder.ecu.unsubscribe(self._on_message)
    
    def test_broadcast_receive_long(self):
        """Test the receivement of a long broadcast message

        For this test we receive the TTI2 (Trip Time Information 2) PGN 65200 (FEB0).
        Its length is 20 Bytes. The contained values are bogous of cause.
        """
        self.feeder.can_messages = [
            (Feeder.MsgType.CANRX, 0x00ECFF01, [32, 20, 0, 3, 255, 0xB0, 0xFE, 0], 0.0),    # TP.CM BAM (to global Address)
            (Feeder.MsgType.CANRX, 0x00EBFF01, [1, 1, 2, 3, 4, 5, 6, 7], 0.0),              # TP.DT 1
            (Feeder.MsgType.CANRX, 0x00EBFF01, [2, 1, 2, 3, 4, 5, 6, 7], 0.0),              # TP.DT 2
            (Feeder.MsgType.CANRX, 0x00EBFF01, [3, 1, 2, 3, 4, 5, 6, 255], 0.0),            # TP.DT 3
        ]

        self.pdus = [
            (Feeder.MsgType.PDU, 65200, [1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6]),
        ]

        self.feeder.ecu.subscribe(self._on_message)
        self.feeder._inject_messages_into_ecu()
        # wait until all messages are processed asynchronously
        while len(self.pdus)>0:
            time.sleep(0.500)
        # wait for final processing    
        time.sleep(0.100)
        self.feeder.ecu.unsubscribe(self._on_message)


    def test_peer_to_peer_receive_short(self):
        """Test the receivement of a normal peer-to-peer message

        For this test we receive the ATS (Anti-theft Status) PGN 56320 (DC00).
        Its length is 8 Bytes. The contained values are bogous of cause.
        """
        self.feeder.can_messages = [
            (Feeder.MsgType.CANRX, 0x00DC0201, [1, 2, 3, 4, 5, 6, 7, 8], 0.0),   # TP.CM RTS
        ]

        self.pdus = [
            (Feeder.MsgType.PDU, 56320, [1, 2, 3, 4, 5, 6, 7, 8], 0),
        ]

        self.feeder.ecu.subscribe(self._on_message)
        self.feeder._inject_messages_into_ecu()
        # wait until all messages are processed asynchronously
        while len(self.pdus)>0:
            time.sleep(0.500)
        # wait for final processing    
        time.sleep(0.100)
        self.feeder.ecu.unsubscribe(self._on_message)

    def test_peer_to_peer_receive_long(self):
        """Test the receivement of a long peer-to-peer message

        For this test we receive the TTI2 (Trip Time Information 2) PGN 65200 (FEB0).
        Its length is 20 Bytes. The contained values are bogous of cause.
        """
        # TODO: we have to select another PGN here! This one is for broadcasting only!
        self.feeder.can_messages = [
            (Feeder.MsgType.CANRX, 0x00EC0201, [16, 20, 0, 3, 1, 176, 254, 0], 0.0),        # TP.CM RTS
            (Feeder.MsgType.CANTX, 0x1CEC0102, [17, 1, 1, 255, 255, 176, 254, 0], 0.0),     # TP.CM CTS 1
            (Feeder.MsgType.CANRX, 0x00EB0201, [1, 1, 2, 3, 4, 5, 6, 7], 0.0),              # TP.DT 1
            (Feeder.MsgType.CANTX, 0x1CEC0102, [17, 1, 2, 255, 255, 176, 254, 0], 0.0),     # TP.CM CTS 2
            (Feeder.MsgType.CANRX, 0x00EB0201, [2, 1, 2, 3, 4, 5, 6, 7], 0.0),              # TP.DT 2
            (Feeder.MsgType.CANTX, 0x1CEC0102, [17, 1, 3, 255, 255, 176, 254, 0], 0.0),     # TP.CM CTS 3
            (Feeder.MsgType.CANRX, 0x00EB0201, [3, 1, 2, 3, 4, 5, 6, 255], 0.0),            # TP.DT 3
            (Feeder.MsgType.CANTX, 0x1CEC0102, [19, 20, 0, 3, 255, 176, 254, 0], 0.0),      # TP.CM EOMACK
        ]

        self.pdus = [
            (Feeder.MsgType.PDU, 65200, [1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6]),
        ]

        self.feeder.ecu.subscribe(self._on_message)
        self.feeder._inject_messages_into_ecu()
        # wait until all messages are processed asynchronously
        while len(self.pdus)>0:
            time.sleep(0.500)
        # wait for final processing    
        time.sleep(0.100)
        self.feeder.ecu.unsubscribe(self._on_message)

    def test_peer_to_peer_send_short(self):
        """Test sending of a short peer-to-peer message

        For this test we send the ERC1 (Electronic Retarder Controller 1) PGN 61440 (F000).
        Its length is 8 Bytes. The contained values are bogous of cause.
        """
        self.feeder.can_messages = [
            (Feeder.MsgType.CANTX, 0x18F09B90, [1, 2, 3, 4, 5, 6, 7, 8], 0.0),      # PGN 61440
        ]

        pdu = (Feeder.MsgType.PDU, 61440, [1, 2, 3, 4, 5, 6, 7, 8])

        self.feeder.ecu.subscribe(self._on_message)

        # sending from 144 to 155 with prio 6
        self.feeder.ecu.send_pgn(0, pdu[1]>>8, 155, 6, 144, pdu[2])
        
        # wait until all messages are processed asynchronously
        while len(self.feeder.can_messages)>0:
            time.sleep(0.500)
        # wait for final processing    
        time.sleep(0.100)
        self.feeder.ecu.unsubscribe(self._on_message)


    def test_peer_to_peer_send_long(self):
        """Test sending of a long peer-to-peer message

        For this test we send a fantasy message with PGN 57088 (DF00).
        Its length is 20 Bytes.
        """
        self.feeder.can_messages = [
            (Feeder.MsgType.CANTX, 0x18EC9B90, [16, 20, 0, 3, 1, 0, 223, 0], 0.0),          # TP.CM RTS 1
            (Feeder.MsgType.CANRX, 0x1CEC909B, [17, 1, 1, 255, 255, 0, 223, 0], 0.0),       # TP.CM CTS 1
            (Feeder.MsgType.CANTX, 0x1CEB9B90, [1, 1, 2, 3, 4, 5, 6, 7], 0.0),              # TP.DT 1
            (Feeder.MsgType.CANRX, 0x1CEC909B, [17, 1, 2, 255, 255, 0, 223, 0], 0.0),       # TP.CM CTS 2
            (Feeder.MsgType.CANTX, 0x1CEB9B90, [2, 1, 2, 3, 4, 5, 6, 7], 0.0),              # TP.DT 2
            (Feeder.MsgType.CANRX, 0x1CEC909B, [17, 1, 3, 255, 255, 0, 223, 0], 0.0),       # TP.CM CTS 3
            (Feeder.MsgType.CANTX, 0x1CEB9B90, [3, 1, 2, 3, 4, 5, 6, 255], 0.0),            # TP.DT 3
            (Feeder.MsgType.CANRX, 0x1CEC909B, [19, 20, 0, 3, 255, 0, 223, 0], 0.0),        # TP.CM EOMACK
        ]

        self.pdus = [
            (Feeder.MsgType.PDU, 57088, None),
        ]

        pdu = (Feeder.MsgType.PDU, 57088, [1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6])

        self.feeder.ecu.subscribe(self._on_message)
        
        # sending from 144 to 155 with prio 6
        self.feeder.ecu.send_pgn(0, pdu[1]>>8, 155, 6, 144, pdu[2])
        
        # wait until all messages are processed asynchronously
        while len(self.feeder.can_messages)>0:
            time.sleep(0.500)
        # wait for final processing    
        time.sleep(0.100)
        self.feeder.ecu.unsubscribe(self._on_message)

    def test_broadcast_send_long(self):
        """Test sending of a long broadcast message (with BAM)

        For this test we use the TTI2 (Trip Time Information 2) PGN 65200 (FEB0).
        Its length is 20 Bytes. The contained values are bogous of cause.
        """
        self.feeder.can_messages = [
            (Feeder.MsgType.CANTX, 0x18ECFF90, [32, 20, 0, 3, 255, 176, 254, 0], 0.0),      # TP.BAM
            (Feeder.MsgType.CANTX, 0x1CEBFF90, [1, 1, 2, 3, 4, 5, 6, 7], 0.0),              # TP.DT 1
            (Feeder.MsgType.CANTX, 0x1CEBFF90, [2, 1, 2, 3, 4, 5, 6, 7], 0.0),              # TP.DT 2
            (Feeder.MsgType.CANTX, 0x1CEBFF90, [3, 1, 2, 3, 4, 5, 6, 255], 0.0),            # TP.DT 3
        ]

        pdu = (Feeder.MsgType.PDU, 65200, [1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6])

        self.feeder.ecu.subscribe(self._on_message)

        # sending from 144 to GLOABL with prio 6
        self.feeder.ecu.send_pgn(0, pdu[1]>>8, pdu[1], 6, 144, pdu[2])
        
        # wait until all messages are processed asynchronously
        while len(self.feeder.can_messages)>0:
            time.sleep(0.500)
        # wait for final processing    
        time.sleep(0.100)
        self.feeder.ecu.unsubscribe(self._on_message)

if __name__ == '__main__':
    unittest.main()        
