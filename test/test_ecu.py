import time

import can
import pytest

import j1939
from j1939.j1939_21 import J1939_21
from j1939.message_id import MessageId
from test.helpers.feeder import Feeder

# def test_connect(self):
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
        (
            Feeder.MsgType.CANRX,
            0x00ECFF01,
            [32, 20, 0, 3, 255, 0xB0, 0xFE, 0],
            0.0,
        ),  # TP.CM BAM (to global Address)
        (Feeder.MsgType.CANRX, 0x00EBFF01, [1, 1, 2, 3, 4, 5, 6, 7], 0.0),  # TP.DT 1
        (Feeder.MsgType.CANRX, 0x00EBFF01, [2, 1, 2, 3, 4, 5, 6, 7], 0.0),  # TP.DT 2
        (Feeder.MsgType.CANRX, 0x00EBFF01, [3, 1, 2, 3, 4, 5, 6, 255], 0.0),  # TP.DT 3
    ]

    feeder.pdus = [
        (
            Feeder.MsgType.PDU,
            65200,
            [1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6],
        )
    ]

    feeder.receive()


def test_broadcast_receive_out_of_sequence_packet_raises():
    """Reject and terminate a BAM session with an invalid sequence number."""
    sent = []
    notified = []
    dll = J1939_21(
        send_message=lambda *args: sent.append(args),
        job_thread_wakeup=lambda: None,
        notify_subscribers=lambda *args: notified.append(args),
        max_cmdt_packets=1,
        minimum_tp_rts_cts_dt_interval=None,
        minimum_tp_bam_dt_interval=None,
        ecu_is_message_acceptable=lambda dest: True,
    )
    bam_mid = MessageId(can_id=0x00ECFF01)
    dll._process_tp_cm(bam_mid, 0xFF, [32, 20, 0, 3, 255, 0xB0, 0xFE, 0], 0.0)
    buffer_hash = dll._buffer_hash(0x01, 0xFF)
    mid = MessageId(can_id=0x00EBFF01)

    with pytest.raises(ValueError, match='out of sequence'):
        dll._process_tp_dt(mid, 0xFF, [2, 8, 9, 10, 11, 12, 13, 14], 0.0)

    assert sent == []
    assert notified == []
    assert buffer_hash not in dll._rcv_buffer


def test_peer_to_peer_receive_out_of_sequence_packet_aborts(feeder):
    """Reject an out-of-sequence CMDT packet and abort the session."""
    sent = []
    dll = J1939_21(
        send_message=lambda *args: sent.append(args),
        job_thread_wakeup=lambda: None,
        notify_subscribers=lambda *args: None,
        max_cmdt_packets=1,
        minimum_tp_rts_cts_dt_interval=None,
        minimum_tp_bam_dt_interval=None,
        ecu_is_message_acceptable=lambda dest: True,
    )
    rts_mid = MessageId(can_id=0x00EC0201)
    dll._process_tp_cm(rts_mid, 0x02, [16, 20, 0, 3, 1, 0, 223, 0], 0.0)
    sent.clear()

    dt_mid = MessageId(can_id=0x00EB0201)
    with pytest.raises(ValueError, match='out of sequence'):
        dll._process_tp_dt(dt_mid, 0x02, [2, 1, 2, 3, 4, 5, 6, 7], 0.0)

    assert sent == [
        (
            0x1CEC0102,
            True,
            [255, 7, 255, 255, 255, 0, 223, 0],
        )
    ]
    assert not dll._rcv_buffer

    dll._process_tp_cm(rts_mid, 0x02, [16, 20, 0, 3, 1, 0, 223, 0], 0.0)
    sent.clear()

    with pytest.raises(ValueError, match='out of sequence'):
        dll._process_tp_dt(dt_mid, 0x02, [0, 1, 2, 3, 4, 5, 6, 7], 0.0)

    assert sent[0][2][1] == 7


def test_peer_to_peer_sequence_gap_after_valid_packet_aborts(feeder):
    """Reject a sequence gap without delivering a partial RTS/CTS payload."""
    sent = []
    notified = []
    dll = J1939_21(
        send_message=lambda *args: sent.append(args),
        job_thread_wakeup=lambda: None,
        notify_subscribers=lambda *args: notified.append(args),
        max_cmdt_packets=2,
        minimum_tp_rts_cts_dt_interval=None,
        minimum_tp_bam_dt_interval=None,
        ecu_is_message_acceptable=lambda dest: True,
    )
    rts_mid = MessageId(can_id=0x00EC0201)
    dll._process_tp_cm(rts_mid, 0x02, [16, 20, 0, 3, 2, 0, 223, 0], 0.0)
    sent.clear()

    dt_mid = MessageId(can_id=0x00EB0201)
    dll._process_tp_dt(dt_mid, 0x02, [1, 1, 2, 3, 4, 5, 6, 7], 0.0)

    with pytest.raises(ValueError, match='out of sequence'):
        dll._process_tp_dt(dt_mid, 0x02, [3, 8, 9, 10, 11, 12, 13, 14], 0.0)

    assert sent[0][2][1] == 7
    assert notified == []
    assert not dll._rcv_buffer


def test_peer_to_peer_receive_short(feeder):
    """Test the receivement of a normal peer-to-peer message

    For this test we receive the ATS (Anti-theft Status) PGN 56320 (DC00).
    Its length is 8 Bytes. The contained values are bogous of cause.
    """
    feeder.accept_all_messages()

    feeder.can_messages = [
        (Feeder.MsgType.CANRX, 0x00DC0201, [1, 2, 3, 4, 5, 6, 7, 8], 0.0),  # TP.CM RTS
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
        (
            Feeder.MsgType.CANRX,
            0x00EC0201,
            [16, 20, 0, 3, 1, 176, 254, 0],
            0.0,
        ),  # TP.CM RTS
        (
            Feeder.MsgType.CANTX,
            0x1CEC0102,
            [17, 1, 1, 255, 255, 176, 254, 0],
            0.0,
        ),  # TP.CM CTS 1
        (Feeder.MsgType.CANRX, 0x00EB0201, [1, 1, 2, 3, 4, 5, 6, 7], 0.0),  # TP.DT 1
        (
            Feeder.MsgType.CANTX,
            0x1CEC0102,
            [17, 1, 2, 255, 255, 176, 254, 0],
            0.0,
        ),  # TP.CM CTS 2
        (Feeder.MsgType.CANRX, 0x00EB0201, [2, 1, 2, 3, 4, 5, 6, 7], 0.0),  # TP.DT 2
        (
            Feeder.MsgType.CANTX,
            0x1CEC0102,
            [17, 1, 3, 255, 255, 176, 254, 0],
            0.0,
        ),  # TP.CM CTS 3
        (Feeder.MsgType.CANRX, 0x00EB0201, [3, 1, 2, 3, 4, 5, 6, 255], 0.0),  # TP.DT 3
        (
            Feeder.MsgType.CANTX,
            0x1CEC0102,
            [19, 20, 0, 3, 255, 176, 254, 0],
            0.0,
        ),  # TP.CM EOMACK
    ]

    feeder.pdus = [
        (
            Feeder.MsgType.PDU,
            65200,
            [1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6],
        )
    ]

    feeder.receive()


def test_peer_to_peer_send_short(feeder):
    """Test sending of a short peer-to-peer message

    For this test we send the ERC1 (Electronic Retarder Controller 1) PGN 61440 (F000).
    Its length is 8 Bytes. The contained values are bogous of cause.
    """
    feeder.can_messages = [
        (Feeder.MsgType.CANTX, 0x18F09B90, [1, 2, 3, 4, 5, 6, 7, 8], 0.0),  # PGN 61440
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
        (
            Feeder.MsgType.CANTX,
            0x18EC9B90,
            [16, 20, 0, 3, 1, 0, 223, 0],
            0.0,
        ),  # TP.CM RTS 1
        (
            Feeder.MsgType.CANRX,
            0x1CEC909B,
            [17, 1, 1, 255, 255, 0, 223, 0],
            0.0,
        ),  # TP.CM CTS 1
        (Feeder.MsgType.CANTX, 0x1CEB9B90, [1, 1, 2, 3, 4, 5, 6, 7], 0.0),  # TP.DT 1
        (
            Feeder.MsgType.CANRX,
            0x1CEC909B,
            [17, 1, 2, 255, 255, 0, 223, 0],
            0.0,
        ),  # TP.CM CTS 2
        (Feeder.MsgType.CANTX, 0x1CEB9B90, [2, 1, 2, 3, 4, 5, 6, 7], 0.0),  # TP.DT 2
        (
            Feeder.MsgType.CANRX,
            0x1CEC909B,
            [17, 1, 3, 255, 255, 0, 223, 0],
            0.0,
        ),  # TP.CM CTS 3
        (Feeder.MsgType.CANTX, 0x1CEB9B90, [3, 1, 2, 3, 4, 5, 6, 255], 0.0),  # TP.DT 3
        (
            Feeder.MsgType.CANRX,
            0x1CEC909B,
            [19, 20, 0, 3, 255, 0, 223, 0],
            0.0,
        ),  # TP.CM EOMACK
    ]

    feeder.pdus = [(Feeder.MsgType.PDU, 57088, None)]

    pdu = (
        Feeder.MsgType.PDU,
        57088,
        [1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6],
    )

    feeder.send(pdu, 144, 155)


def test_broadcast_send_long(feeder):
    """Test sending of a long broadcast message (with BAM)

    For this test we use the TTI2 (Trip Time Information 2) PGN 65200 (FEB0).
    Its length is 20 Bytes. The contained values are bogous of cause.
    """
    feeder.can_messages = [
        (
            Feeder.MsgType.CANTX,
            0x18ECFF90,
            [32, 20, 0, 3, 255, 176, 254, 0],
            0.0,
        ),  # TP.BAM
        (Feeder.MsgType.CANTX, 0x1CEBFF90, [1, 1, 2, 3, 4, 5, 6, 7], 0.0),  # TP.DT 1
        (Feeder.MsgType.CANTX, 0x1CEBFF90, [2, 1, 2, 3, 4, 5, 6, 7], 0.0),  # TP.DT 2
        (Feeder.MsgType.CANTX, 0x1CEBFF90, [3, 1, 2, 3, 4, 5, 6, 255], 0.0),  # TP.DT 3
    ]

    pdu = (
        Feeder.MsgType.PDU,
        65200,
        [1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6],
    )

    feeder.send(pdu, 144, pdu[1])


def test_add_bus(feeder):
    """
    Test adding and removing a bus to the ECU
    """
    bus = can.interface.Bus(interface="virtual", channel=1)
    feeder.ecu.add_bus(bus)
    assert feeder.ecu._bus == bus
    feeder.ecu.remove_bus()
    assert feeder.ecu._bus is None


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
    assert feeder.ecu._notifier is None


def test_add_notifier_after_notifier_stop_still_delivers(feeder):
    """A listener stopped via notifier.stop() must work when re-added later.

    Regression test for a bug where ElectronicControlUnit.add_notifier()
    re-added the ECU's own MessageListener (created once, in __init__, and
    reused for the ECU's whole lifetime) to a new notifier without
    resetting listener.stopped -- can.Notifier.stop() sets that flag
    permanently on every listener it holds, so once *any* notifier this
    ECU had been added to was stopped, every future notifier it was added
    to (even a brand new one) silently dropped every frame forever,
    despite the notifier itself being alive and the listener being
    registered on it.
    """
    bus = can.interface.Bus(interface="virtual", channel="notifier-reset-test")
    try:
        feeder.ecu.add_bus(bus)

        notifier1 = can.Notifier(bus=bus, listeners=[])
        feeder.ecu.add_notifier(notifier1)
        notifier1.stop()
        feeder.ecu.remove_notifier()

        notifier2 = can.Notifier(bus=bus, listeners=[])
        feeder.ecu.add_notifier(notifier2)

        received = []
        feeder.ecu.subscribe(
            lambda priority, pgn, sa, timestamp, data: received.append(data)
        )

        sender = can.interface.Bus(interface="virtual", channel="notifier-reset-test")
        try:
            msg = can.Message(
                arbitration_id=0x18FEB201,
                data=[1, 2, 3, 4, 5, 6, 7, 8],
                is_extended_id=True,
            )
            sender.send(msg)

            for _ in range(50):
                if received:
                    break
                time.sleep(0.01)

            assert received, (
                "Frame was not delivered after re-adding to a new notifier -- "
                "listener.stopped was not reset"
            )
        finally:
            notifier2.stop()
            sender.shutdown()
    finally:
        bus.shutdown()


def test_add_bus_filters(feeder):
    """
    Test adding bus filters to the ECU
    """
    bus = can.interface.Bus(interface="virtual", channel=1)
    feeder.ecu.add_bus(bus)
    filters = [
        {"can_id": 0x123, "can_mask": 0x7FF, "extended": True},
        {"can_id": 0x456, "can_mask": 0x7FF},
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


def test_constructor_accepts_bus_instance():
    """Passing a bus instance to the constructor stores it without calling connect()."""
    bus = can.interface.Bus(interface="virtual", channel="test_ctor_bus")
    ecu = None
    try:
        ecu = j1939.ElectronicControlUnit(bus=bus)
        assert ecu._bus is bus
        assert ecu._notifier is None  # connect() not yet called
        assert ecu._bus_created is False  # bus was not created by this ECU
    finally:
        if ecu is not None:
            ecu.stop()
        bus.shutdown()


def test_constructor_bus_none_by_default():
    """Without a bus= argument, _bus starts as None."""
    ecu = j1939.ElectronicControlUnit(send_message=lambda *a, **kw: None)
    try:
        assert ecu._bus is None
        assert ecu._bus_created is False
    finally:
        ecu.stop()


def test_constructor_invalid_data_link_layer_raises():
    """An unsupported data_link_layer string raises ValueError immediately."""
    import pytest

    with pytest.raises(ValueError, match="j1939-21.*j1939-22"):
        j1939.ElectronicControlUnit(data_link_layer="j1939-99")


def test_connect_with_preexisting_bus_sets_notifier():
    """When a bus is passed to __init__, connect() sets up the notifier
    without creating a new bus and without emitting a DeprecationWarning.
    """
    import warnings

    bus = can.interface.Bus(interface="virtual", channel="test_connect_prebus")
    ecu = None
    try:
        ecu = j1939.ElectronicControlUnit(bus=bus)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            returned_bus = ecu.connect()

        # No DeprecationWarning: bus was already provided
        deprecations = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert deprecations == [], (
            "connect() must not warn when bus was provided in constructor"
        )

        assert returned_bus is bus
        assert ecu._notifier is not None
        assert ecu._bus is bus
    finally:
        if ecu is not None:
            ecu.disconnect()
            ecu.stop()
        bus.shutdown()


def test_connect_without_preexisting_bus_emits_deprecation_warning():
    """When connect() creates the bus itself (legacy path), it emits a
    DeprecationWarning advising the caller to pass bus= to the constructor.
    """
    import warnings

    ecu = j1939.ElectronicControlUnit(send_message=lambda *a, **kw: None)
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ecu.connect(interface="virtual", channel="test_connect_legacy")

        deprecations = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecations) == 1
        assert "deprecated" in str(deprecations[0].message).lower()
        assert ecu._bus_created is True
    finally:
        ecu.disconnect()
        ecu.stop()


def test_disconnect_before_connect_raises_runtime_error():
    """Calling disconnect() before connect() raises RuntimeError (previously
    would crash with AttributeError/NoneType errors).
    """
    import pytest

    ecu = j1939.ElectronicControlUnit(send_message=lambda *a, **kw: None)
    try:
        with pytest.raises(RuntimeError):
            ecu.disconnect()
    finally:
        ecu.stop()


def test_disconnect_does_not_shutdown_external_bus():
    """When a bus was passed to __init__ (not created by connect()), disconnect()
    must NOT call bus.shutdown() — the caller owns the bus lifecycle.
    """
    shutdown_called = []

    class TrackingBus(can.interfaces.virtual.VirtualBus):
        def shutdown(self):
            shutdown_called.append(True)
            super().shutdown()

    bus = TrackingBus(channel="test_disconnect_external")
    ecu = None
    try:
        ecu = j1939.ElectronicControlUnit(bus=bus)
        ecu.connect()
        ecu.disconnect()

        assert shutdown_called == [], (
            "disconnect() must not shutdown a bus that was provided externally"
        )
    finally:
        if ecu is not None:
            ecu.stop()
        bus.shutdown()
