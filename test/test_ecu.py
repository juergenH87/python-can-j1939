import time

import can
import pytest
import j1939
from j1939.iso11783_etp import ISO11783_ETP
from test_helpers.feeder import Feeder
from test_helpers.conftest import feeder


@pytest.fixture()
def etp_feeder():
    """Feeder requesting 255 ETP packets per CTS so ETP tests don't need 256+ CTS rounds."""
    f = Feeder(max_etp_cmdt_packets=255)
    yield f
    f.stop()


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

    # the EOM_ACK reaches subscribers as its CM frame, under the transferred PGN
    feeder.pdus = [(Feeder.MsgType.PDU, 57088, [19, 20, 0, 3, 255, 0, 223, 0])]

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

def _etp_pgn_bytes(pgn):
    return [pgn & 0xFF, (pgn >> 8) & 0xFF, (pgn >> 16) & 0xFF]


def _etp_size_bytes(size):
    return [size & 0xFF, (size >> 8) & 0xFF, (size >> 16) & 0xFF, (size >> 24) & 0xFF]


def _etp_offset_bytes(value):
    return [value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF]


def test_peer_to_peer_receive_etp(etp_feeder):
    """ISO 11783-3 ETP receive: a destination-specific message > 1785 bytes.

    1786 bytes = 256 ETP.DT packets (last packet carries 1 data byte + 6 pad bytes).
    With max_cmdt_packets=255 the receiver requests 255 packets in the first
    burst and 1 in the second.
    """
    feeder = etp_feeder
    feeder.accept_all_messages()

    src = 0x01
    dst = 0x02
    pgn = 0xDF00  # PDU1 destination-specific PGN (PF=223)
    message_size = 1786
    num_packets = (message_size + 6) // 7  # 256
    payload = [(i & 0xFF) for i in range(message_size)]

    cm_id_rx = 0x00C80000 | (dst << 8) | src       # peer -> us
    cm_id_tx = 0x1CC80000 | (src << 8) | dst       # us  -> peer (priority 7)
    dt_id_rx = 0x00C70000 | (dst << 8) | src       # peer -> us

    messages = []
    messages.append((Feeder.MsgType.CANRX, cm_id_rx,
                     [20] + _etp_size_bytes(message_size) + _etp_pgn_bytes(pgn), 0.0))
    messages.append((Feeder.MsgType.CANTX, cm_id_tx,
                     [21, 255] + _etp_offset_bytes(1) + _etp_pgn_bytes(pgn), 0.0))
    messages.append((Feeder.MsgType.CANRX, cm_id_rx,
                     [22, 255] + _etp_offset_bytes(0) + _etp_pgn_bytes(pgn), 0.0))
    for seq in range(1, 256):
        chunk = payload[(seq - 1) * 7:seq * 7]
        messages.append((Feeder.MsgType.CANRX, dt_id_rx, [seq] + chunk, 0.0))
    # Burst 2: request 1 more packet
    messages.append((Feeder.MsgType.CANTX, cm_id_tx,
                     [21, 1] + _etp_offset_bytes(256) + _etp_pgn_bytes(pgn), 0.0))
    messages.append((Feeder.MsgType.CANRX, cm_id_rx,
                     [22, 1] + _etp_offset_bytes(255) + _etp_pgn_bytes(pgn), 0.0))
    last = payload[(num_packets - 1) * 7:]
    last += [0xFF] * (7 - len(last))
    messages.append((Feeder.MsgType.CANRX, dt_id_rx, [1] + last, 0.0))
    # Final EOMA from us
    messages.append((Feeder.MsgType.CANTX, cm_id_tx,
                     [23] + _etp_size_bytes(message_size) + _etp_pgn_bytes(pgn), 0.0))

    feeder.can_messages = messages
    feeder.pdus = [(Feeder.MsgType.PDU, pgn, payload)]
    feeder.receive()


def test_peer_to_peer_send_etp(etp_feeder):
    """ISO 11783-3 ETP send: a destination-specific message > 1785 bytes."""
    feeder = etp_feeder
    feeder.accept_all_messages()

    src = 0x90
    dst = 0x9B
    pgn = 0xDF00  # PDU1 destination-specific PGN (PF=223)
    message_size = 1786
    num_packets = (message_size + 6) // 7  # 256
    payload = [(i & 0xFF) for i in range(message_size)]

    cm_id_tx_p7 = 0x1CC80000 | (dst << 8) | src   # us -> peer (priority 7)
    cm_id_rx_p7 = 0x1CC80000 | (src << 8) | dst
    dt_id_tx = 0x1CC70000 | (dst << 8) | src   # us -> peer (priority 7)

    messages = []
    # ETP.CM is always sent at priority 7, whatever the caller's priority
    messages.append((Feeder.MsgType.CANTX, cm_id_tx_p7,
                     [20] + _etp_size_bytes(message_size) + _etp_pgn_bytes(pgn), 0.0))
    # Peer responds with CTS for the full first burst
    messages.append((Feeder.MsgType.CANRX, cm_id_rx_p7,
                     [21, 255] + _etp_offset_bytes(1) + _etp_pgn_bytes(pgn), 0.0))
    # We answer with DPO then 255 DTs
    messages.append((Feeder.MsgType.CANTX, cm_id_tx_p7,
                     [22, 255] + _etp_offset_bytes(0) + _etp_pgn_bytes(pgn), 0.0))
    for seq in range(1, 256):
        chunk = payload[(seq - 1) * 7:seq * 7]
        messages.append((Feeder.MsgType.CANTX, dt_id_tx, [seq] + chunk, 0.0))
    # Peer requests the final packet
    messages.append((Feeder.MsgType.CANRX, cm_id_rx_p7,
                     [21, 1] + _etp_offset_bytes(256) + _etp_pgn_bytes(pgn), 0.0))
    messages.append((Feeder.MsgType.CANTX, cm_id_tx_p7,
                     [22, 1] + _etp_offset_bytes(255) + _etp_pgn_bytes(pgn), 0.0))
    last = payload[(num_packets - 1) * 7:]
    last += [0xFF] * (7 - len(last))
    messages.append((Feeder.MsgType.CANTX, dt_id_tx, [1] + last, 0.0))
    # Peer's EOMA closes the session
    messages.append((Feeder.MsgType.CANRX, cm_id_rx_p7,
                     [23] + _etp_size_bytes(message_size) + _etp_pgn_bytes(pgn), 0.0))

    feeder.can_messages = messages
    # the EOM_ACK reaches subscribers as its CM frame, under the transferred PGN
    feeder.pdus = [(Feeder.MsgType.PDU, pgn, [23] + _etp_size_bytes(message_size) + _etp_pgn_bytes(pgn))]

    pdu = (Feeder.MsgType.PDU, pgn, payload)
    feeder.send(pdu, src, dst)


def _etp_abort_payload(reason, pgn):
    return [255, reason, 0xFF, 0xFF, 0xFF] + _etp_pgn_bytes(pgn)


def _drive_until_drained(feeder, timeout=3.0):
    feeder.ecu.subscribe(feeder._on_message)
    feeder._inject_messages_into_ecu()
    deadline = time.time() + timeout
    while feeder.can_messages and time.time() < deadline:
        time.sleep(0.05)
    feeder.ecu.unsubscribe(feeder._on_message)
    feeder.check()
    assert not feeder.can_messages, f"expected messages not consumed: {feeder.can_messages}"


def test_etp_receive_rts_size_too_large(etp_feeder):
    """RTS with size > MAX_MESSAGE_SIZE must be aborted with ANY_OTHER_REASON."""
    feeder = etp_feeder
    feeder.accept_all_messages()
    src, dst = 0x01, 0x02
    pgn = 0xDF00
    bad_size = ISO11783_ETP.MAX_MESSAGE_SIZE + 1
    cm_id_rx = 0x00C80000 | (dst << 8) | src
    cm_id_tx = 0x1CC80000 | (src << 8) | dst

    feeder.can_messages = [
        (Feeder.MsgType.CANRX, cm_id_rx,
         [20] + _etp_size_bytes(bad_size) + _etp_pgn_bytes(pgn), 0.0),
        (Feeder.MsgType.CANTX, cm_id_tx,
         _etp_abort_payload(ISO11783_ETP.AbortReason.ANY_OTHER_REASON, pgn), 0.0),
    ]
    feeder.pdus = []
    _drive_until_drained(feeder)


def test_etp_receive_repeated_rts_restarts(etp_feeder):
    """A second RTS for the same PGN replaces the open connection: it is
    answered with a fresh CTS from packet 1, not an abort."""
    feeder = etp_feeder
    feeder.accept_all_messages()
    src, dst = 0x01, 0x02
    pgn = 0xDF00
    size = 2000
    burst = min(255, (size + 6) // 7)
    cm_id_rx = 0x00C80000 | (dst << 8) | src
    cm_id_tx = 0x1CC80000 | (src << 8) | dst

    feeder.can_messages = [
        (Feeder.MsgType.CANRX, cm_id_rx,
         [20] + _etp_size_bytes(size) + _etp_pgn_bytes(pgn), 0.0),
        (Feeder.MsgType.CANTX, cm_id_tx,
         [21, burst] + _etp_offset_bytes(1) + _etp_pgn_bytes(pgn), 0.0),
        (Feeder.MsgType.CANRX, cm_id_rx,
         [20] + _etp_size_bytes(size) + _etp_pgn_bytes(pgn), 0.0),
        (Feeder.MsgType.CANTX, cm_id_tx,
         [21, burst] + _etp_offset_bytes(1) + _etp_pgn_bytes(pgn), 0.0),
    ]
    feeder.pdus = []
    _drive_until_drained(feeder)


def test_etp_receive_rts_for_other_pgn_aborts_busy(etp_feeder):
    """An RTS for another PGN while an ETP session is active must yield a
    BUSY abort, and leave the open connection alone."""
    feeder = etp_feeder
    feeder.accept_all_messages()
    src, dst = 0x01, 0x02
    pgn = 0xDF00
    other_pgn = 0xDE00
    size = 2000
    burst = min(255, (size + 6) // 7)
    cm_id_rx = 0x00C80000 | (dst << 8) | src
    cm_id_tx = 0x1CC80000 | (src << 8) | dst

    feeder.can_messages = [
        (Feeder.MsgType.CANRX, cm_id_rx,
         [20] + _etp_size_bytes(size) + _etp_pgn_bytes(pgn), 0.0),
        (Feeder.MsgType.CANTX, cm_id_tx,
         [21, burst] + _etp_offset_bytes(1) + _etp_pgn_bytes(pgn), 0.0),
        (Feeder.MsgType.CANRX, cm_id_rx,
         [20] + _etp_size_bytes(size) + _etp_pgn_bytes(other_pgn), 0.0),
        (Feeder.MsgType.CANTX, cm_id_tx,
         _etp_abort_payload(ISO11783_ETP.AbortReason.BUSY, other_pgn), 0.0),
    ]
    feeder.pdus = []
    _drive_until_drained(feeder)
    assert feeder.ecu.j1939_dll.etp.has_receive_session(src, dst)


def test_etp_receive_dpo_offset_mismatch(etp_feeder):
    """DPO with offset != expected must be aborted with BAD_DPO_OFFSET."""
    feeder = etp_feeder
    feeder.accept_all_messages()
    src, dst = 0x01, 0x02
    pgn = 0xDF00
    size = 2000
    burst = min(255, (size + 6) // 7)
    cm_id_rx = 0x00C80000 | (dst << 8) | src
    cm_id_tx = 0x1CC80000 | (src << 8) | dst

    feeder.can_messages = [
        (Feeder.MsgType.CANRX, cm_id_rx,
         [20] + _etp_size_bytes(size) + _etp_pgn_bytes(pgn), 0.0),
        (Feeder.MsgType.CANTX, cm_id_tx,
         [21, burst] + _etp_offset_bytes(1) + _etp_pgn_bytes(pgn), 0.0),
        # Expected DPO offset is 0; send 99 instead.
        (Feeder.MsgType.CANRX, cm_id_rx,
         [22, burst] + _etp_offset_bytes(99) + _etp_pgn_bytes(pgn), 0.0),
        (Feeder.MsgType.CANTX, cm_id_tx,
         _etp_abort_payload(ISO11783_ETP.AbortReason.BAD_DPO_OFFSET, pgn), 0.0),
    ]
    feeder.pdus = []
    _drive_until_drained(feeder)


def test_etp_receive_dt_bad_sequence(etp_feeder):
    """DT with non-monotonic sequence number must be aborted with BAD_SEQUENCE."""
    feeder = etp_feeder
    feeder.accept_all_messages()
    src, dst = 0x01, 0x02
    pgn = 0xDF00
    size = 2000
    burst = min(255, (size + 6) // 7)
    cm_id_rx = 0x00C80000 | (dst << 8) | src
    cm_id_tx = 0x1CC80000 | (src << 8) | dst
    dt_id_rx = 0x00C70000 | (dst << 8) | src
    payload = [(i & 0xFF) for i in range(size)]

    feeder.can_messages = [
        (Feeder.MsgType.CANRX, cm_id_rx,
         [20] + _etp_size_bytes(size) + _etp_pgn_bytes(pgn), 0.0),
        (Feeder.MsgType.CANTX, cm_id_tx,
         [21, burst] + _etp_offset_bytes(1) + _etp_pgn_bytes(pgn), 0.0),
        (Feeder.MsgType.CANRX, cm_id_rx,
         [22, burst] + _etp_offset_bytes(0) + _etp_pgn_bytes(pgn), 0.0),
        (Feeder.MsgType.CANRX, dt_id_rx, [1] + payload[0:7], 0.0),
        # Skip seq 2 to trigger BAD_SEQUENCE
        (Feeder.MsgType.CANRX, dt_id_rx, [3] + payload[7:14], 0.0),
        (Feeder.MsgType.CANTX, cm_id_tx,
         _etp_abort_payload(ISO11783_ETP.AbortReason.BAD_SEQUENCE, pgn), 0.0),
    ]
    feeder.pdus = []
    _drive_until_drained(feeder)


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
