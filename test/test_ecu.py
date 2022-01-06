import time

import j1939
from feeder import Feeder



def receive(feeder):
    feeder.ecu.subscribe(on_message)
    feeder.inject_messages_into_ecu()
    # wait until all messages are processed asynchronously
    while len(pdus)>0:
        time.sleep(0.500)
    # wait for final processing    
    time.sleep(0.100)
    feeder.ecu.unsubscribe(on_message)


def send(feeder, pdu, source, destination):
    feeder.ecu.subscribe(on_message)

    # sending from 240 to 155 with prio 6
    feeder.ecu.send_pgn(0, pdu[1]>>8, destination, 6, source, pdu[2])
    
    # wait until all messages are processed asynchronously
    while len(feeder.can_messages)>0:
        time.sleep(0.500)
    # wait for final processing    
    time.sleep(0.100)
    feeder.ecu.unsubscribe(on_message)

#def test_connect(self):
#    self.feeder.ecu.connect(bustype="virtual", channel=1)
#    self.feeder.ecu.disconnect()

def test_broadcast_receive_short(feeder):
    """Test the receivement of a normal broadcast message

    For this test we receive the GFI1 (Fuel Information 1 (Gaseous)) PGN 65202 (FEB2).
    Its length is 8 Bytes. The contained values are bogous of cause.
    """
    feeder.accept_all_messages()

    feeder.can_messages = [
        (Feeder.MsgType.CANRX, 0x00FEB201, [1, 2, 3, 4, 5, 6, 7, 8], 0.0),
    ]

    feeder.pdus = [(Feeder.MsgType.PDU, 65202, [1, 2, 3, 4, 5, 6, 7, 8])]

    feeder.receive()

def test_broadcast_receive_long(feeder):
    """Test the receivement of a long broadcast message

    For this test we receive the TTI2 (Trip Time Information 2) PGN 65200 (FEB0).
    Its length is 20 Bytes. The contained values are bogous of cause.
    """
    feeder.accept_all_messages()

    feeder.can_messages = [
        (Feeder.MsgType.CANRX, 0x00ECFF01, [32, 20, 0, 3, 255, 0xB0, 0xFE, 0], 0.0),    # TP.CM BAM (to global Address)
        (Feeder.MsgType.CANRX, 0x00EBFF01, [1, 1, 2, 3, 4, 5, 6, 7], 0.0),              # TP.DT 1
        (Feeder.MsgType.CANRX, 0x00EBFF01, [2, 1, 2, 3, 4, 5, 6, 7], 0.0),              # TP.DT 2
        (Feeder.MsgType.CANRX, 0x00EBFF01, [3, 1, 2, 3, 4, 5, 6, 255], 0.0),            # TP.DT 3
    ]

    feeder.pdus = [(Feeder.MsgType.PDU, 65200, [1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6])]

    feeder.receive()


def test_peer_to_peer_receive_short(feeder):
    """Test the receivement of a normal peer-to-peer message

    For this test we receive the ATS (Anti-theft Status) PGN 56320 (DC00).
    Its length is 8 Bytes. The contained values are bogous of cause.
    """
    feeder.accept_all_messages()

    feeder.can_messages = [
        (Feeder.MsgType.CANRX, 0x00DC0201, [1, 2, 3, 4, 5, 6, 7, 8], 0.0),   # TP.CM RTS
    ]

    feeder.pdus = [(Feeder.MsgType.PDU, 56320, [1, 2, 3, 4, 5, 6, 7, 8], 0)]

    feeder.receive()

def test_peer_to_peer_receive_long(feeder):
    """Test the receivement of a long peer-to-peer message

    For this test we receive the TTI2 (Trip Time Information 2) PGN 65200 (FEB0).
    Its length is 20 Bytes. The contained values are bogous of cause.
    """
    feeder.accept_all_messages()
    # TODO: we have to select another PGN here! This one is for broadcasting only!
    feeder.can_messages = [
        (Feeder.MsgType.CANRX, 0x00EC0201, [16, 20, 0, 3, 1, 176, 254, 0], 0.0),        # TP.CM RTS
        (Feeder.MsgType.CANTX, 0x1CEC0102, [17, 1, 1, 255, 255, 176, 254, 0], 0.0),     # TP.CM CTS 1
        (Feeder.MsgType.CANRX, 0x00EB0201, [1, 1, 2, 3, 4, 5, 6, 7], 0.0),              # TP.DT 1
        (Feeder.MsgType.CANTX, 0x1CEC0102, [17, 1, 2, 255, 255, 176, 254, 0], 0.0),     # TP.CM CTS 2
        (Feeder.MsgType.CANRX, 0x00EB0201, [2, 1, 2, 3, 4, 5, 6, 7], 0.0),              # TP.DT 2
        (Feeder.MsgType.CANTX, 0x1CEC0102, [17, 1, 3, 255, 255, 176, 254, 0], 0.0),     # TP.CM CTS 3
        (Feeder.MsgType.CANRX, 0x00EB0201, [3, 1, 2, 3, 4, 5, 6, 255], 0.0),            # TP.DT 3
        (Feeder.MsgType.CANTX, 0x1CEC0102, [19, 20, 0, 3, 255, 176, 254, 0], 0.0),      # TP.CM EOMACK
    ]

    feeder.pdus = [(Feeder.MsgType.PDU, 65200, [1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6])]

    feeder.receive()

def test_peer_to_peer_send_short(feeder):
    """Test sending of a short peer-to-peer message

    For this test we send the ERC1 (Electronic Retarder Controller 1) PGN 61440 (F000).
    Its length is 8 Bytes. The contained values are bogous of cause.
    """
    feeder.can_messages = [
        (Feeder.MsgType.CANTX, 0x18F09B90, [1, 2, 3, 4, 5, 6, 7, 8], 0.0),      # PGN 61440
    ]

    pdu = (Feeder.MsgType.PDU, 61440, [1, 2, 3, 4, 5, 6, 7, 8])

    feeder.send(pdu, 144, 155)


def test_peer_to_peer_send_long(feeder):
    """Test sending of a long peer-to-peer message

    For this test we send a fantasy message with PGN 57088 (DF00).
    Its length is 20 Bytes.
    """
    feeder.accept_all_messages()

    feeder.can_messages = [
        (Feeder.MsgType.CANTX, 0x18EC9B90, [16, 20, 0, 3, 1, 0, 223, 0], 0.0),          # TP.CM RTS 1
        (Feeder.MsgType.CANRX, 0x1CEC909B, [17, 1, 1, 255, 255, 0, 223, 0], 0.0),       # TP.CM CTS 1
        (Feeder.MsgType.CANTX, 0x1CEB9B90, [1, 1, 2, 3, 4, 5, 6, 7], 0.0),              # TP.DT 1
        (Feeder.MsgType.CANRX, 0x1CEC909B, [17, 1, 2, 255, 255, 0, 223, 0], 0.0),       # TP.CM CTS 2
        (Feeder.MsgType.CANTX, 0x1CEB9B90, [2, 1, 2, 3, 4, 5, 6, 7], 0.0),              # TP.DT 2
        (Feeder.MsgType.CANRX, 0x1CEC909B, [17, 1, 3, 255, 255, 0, 223, 0], 0.0),       # TP.CM CTS 3
        (Feeder.MsgType.CANTX, 0x1CEB9B90, [3, 1, 2, 3, 4, 5, 6, 255], 0.0),            # TP.DT 3
        (Feeder.MsgType.CANRX, 0x1CEC909B, [19, 20, 0, 3, 255, 0, 223, 0], 0.0),        # TP.CM EOMACK
    ]

    feeder.pdus = [(Feeder.MsgType.PDU, 57088, None)]

    pdu = (Feeder.MsgType.PDU, 57088, [1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6])

    feeder.send(pdu, 144, 155)

def test_broadcast_send_long(feeder):
    """Test sending of a long broadcast message (with BAM)

    For this test we use the TTI2 (Trip Time Information 2) PGN 65200 (FEB0).
    Its length is 20 Bytes. The contained values are bogous of cause.
    """
    feeder.can_messages = [
        (Feeder.MsgType.CANTX, 0x18ECFF90, [32, 20, 0, 3, 255, 176, 254, 0], 0.0),      # TP.BAM
        (Feeder.MsgType.CANTX, 0x1CEBFF90, [1, 1, 2, 3, 4, 5, 6, 7], 0.0),              # TP.DT 1
        (Feeder.MsgType.CANTX, 0x1CEBFF90, [2, 1, 2, 3, 4, 5, 6, 7], 0.0),              # TP.DT 2
        (Feeder.MsgType.CANTX, 0x1CEBFF90, [3, 1, 2, 3, 4, 5, 6, 255], 0.0),            # TP.DT 3
    ]

    pdu = (Feeder.MsgType.PDU, 65200, [1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6])

    feeder.send(pdu, 144, pdu[1])

