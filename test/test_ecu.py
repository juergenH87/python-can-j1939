import time
from unittest.mock import Mock

import can
import j1939
import pytest
from test_helpers.feeder import Feeder
from test_helpers.conftest import feeder


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


def test_disconnect_is_idempotent(feeder):
    bus = Mock()
    notifier = Mock()
    feeder.ecu.add_bus(bus)
    feeder.ecu.add_notifier(notifier)

    feeder.ecu.disconnect()
    feeder.ecu.disconnect()

    notifier.stop.assert_called_once_with()
    bus.shutdown.assert_called_once_with()
    assert feeder.ecu._notifier is notifier
    assert feeder.ecu._bus is None


def test_disconnect_without_connection(feeder):
    feeder.ecu.disconnect()
    feeder.ecu.disconnect()
    assert feeder.ecu._notifier is None
    assert feeder.ecu._bus is None


def test_disconnect_with_partial_connection(feeder):
    bus = Mock()
    feeder.ecu.add_bus(bus)
    feeder.ecu.disconnect()
    feeder.ecu.disconnect()
    bus.shutdown.assert_called_once_with()

    notifier = Mock()
    feeder.ecu.add_notifier(notifier)
    feeder.ecu.disconnect()
    feeder.ecu.disconnect()
    notifier.stop.assert_called_once_with()


def test_disconnect_preserves_notifier_removal(feeder):
    bus = can.interface.Bus(interface="virtual")
    notifier = can.Notifier(bus, [], timeout=0.01)
    feeder.ecu.add_bus(bus)
    feeder.ecu.add_notifier(notifier)

    try:
        feeder.ecu.disconnect()
        assert all(listener in notifier.listeners for listener in feeder.ecu._listeners)

        feeder.ecu.remove_notifier()
        assert all(listener not in notifier.listeners for listener in feeder.ecu._listeners)
        assert feeder.ecu._notifier is None
    finally:
        notifier.stop()
        bus.shutdown()


@pytest.mark.parametrize("failed_resource", ["notifier", "bus"])
def test_disconnect_retries_failed_cleanup(feeder, failed_resource):
    bus = Mock()
    notifier = Mock()
    feeder.ecu.add_bus(bus)
    feeder.ecu.add_notifier(notifier)
    error = RuntimeError("cleanup failed")
    cleanup = notifier.stop if failed_resource == "notifier" else bus.shutdown
    cleanup.side_effect = [error, None]

    with pytest.raises(RuntimeError) as raised:
        feeder.ecu.disconnect()
    assert raised.value is error
    assert feeder.ecu._bus is bus
    if failed_resource == "notifier":
        bus.shutdown.assert_not_called()

    feeder.ecu.disconnect()
    feeder.ecu.disconnect()

    assert notifier.stop.call_count == (2 if failed_resource == "notifier" else 1)
    assert bus.shutdown.call_count == (2 if failed_resource == "bus" else 1)
    assert feeder.ecu._bus is None


@pytest.mark.parametrize("attach", ["connect", "add"])
def test_disconnect_after_reconnection(feeder, monkeypatch, attach):
    for _ in range(2):
        bus = Mock()
        notifier = Mock()
        if attach == "connect":
            monkeypatch.setattr(can.interface, "Bus", Mock(return_value=bus))
            monkeypatch.setattr(can, "Notifier", Mock(return_value=notifier))
            assert feeder.ecu.connect() is bus
        else:
            feeder.ecu.add_bus(bus)
            feeder.ecu.add_notifier(notifier)

        feeder.ecu.disconnect()
        feeder.ecu.disconnect()

        notifier.stop.assert_called_once_with()
        bus.shutdown.assert_called_once_with()


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

def test_add_bus(feeder):
    """
    Test adding and removing a bus to the ECU
    """
    bus = can.interface.Bus(interface="virtual", channel=1)
    feeder.ecu.add_bus(bus)
    assert feeder.ecu._bus == bus
    feeder.ecu.remove_bus()
    assert feeder.ecu._bus == None

def test_add_notfier(feeder):
    """
    Test adding and removing a notifier to the ECU
    """
    bus = can.interface.Bus(interface="virtual", channel=1)
    feeder.ecu.add_bus(bus)
    notifier = can.Notifier(bus=bus, listeners=[])
    feeder.ecu.add_notifier(notifier)
    assert feeder.ecu._notifier == notifier
    feeder.ecu.remove_notifier()
    assert feeder.ecu._notifier == None

def test_add_bus_filters(feeder):
    """
    Test adding bus filters to the ECU
    """
    bus = can.interface.Bus(interface="virtual", channel=1)
    feeder.ecu.add_bus(bus)
    filters = [
        {'can_id': 0x123, 'can_mask': 0x7FF, 'extended': True},
        {'can_id': 0x456, 'can_mask': 0x7FF}
    ]
    feeder.ecu.add_bus_filters(filters)
    assert feeder.ecu._bus.filters == filters

def test_subscribe(feeder):
    """
    Test subscribing to callback
    """
    call_count = 0

    def callback(priority: int, pgn: int, sa: int, timestamp: int, data: bytearray):
        nonlocal call_count
        call_count += 1

    feeder.ecu.subscribe(callback)
    
    feeder.can_messages = [
        (Feeder.MsgType.CANRX, 0x00FEB201, [1, 2, 3, 4, 5, 6, 7, 8], 0.0),
    ]

    feeder.pdus = [(Feeder.MsgType.PDU, 65202, [1, 2, 3, 4, 5, 6, 7, 8])]

    feeder.receive()

    assert call_count == 1
