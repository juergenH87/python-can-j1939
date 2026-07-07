"""Passive observation vs. active participation for directed (PDU1) traffic.

A subscriber registered without an exact owned address (a wildcard
``device_address=None`` monitor) must be able to *observe* directed peer-to-peer
frames addressed to another node, but the stack must not *participate* in the
connection-mode transport protocol (it must not answer RTS with CTS/EOM-ACK) for
destinations it does not own.
"""

import time

import j1939


def _make_ecu():
    """Create an ECU whose transmissions are recorded instead of sent."""
    sent = []

    def record_send(can_id, extended_id, data, fd_format=False):
        sent.append((can_id, list(data)))

    ecu = j1939.ElectronicControlUnit(send_message=record_send)
    return ecu, sent


def test_wildcard_observes_directed_single_frame():
    """A wildcard subscriber receives a directed single-frame PDU1 addressed to
    a third node, and the stack transmits nothing in response."""
    ecu, sent = _make_ecu()
    received = []
    ecu.subscribe(
        lambda priority, pgn, sa, timestamp, data: received.append(
            (pgn, sa, list(data))
        )
    )
    try:
        # Directed single-frame PDU1: PGN 0xEF00 (Proprietary A),
        # destination 0x20, source 0xF9 -> arbitration id 0x18EF20F9.
        ecu.notify(0x18EF20F9, [1, 2, 3, 4, 5, 6, 7, 8], time.time())
        time.sleep(0.1)
    finally:
        ecu.stop()

    assert received == [(0xEF00, 0xF9, [1, 2, 3, 4, 5, 6, 7, 8])]
    assert sent == [], "passive observation must not transmit on the bus"


def test_no_cts_for_rts_directed_at_third_node():
    """A wildcard monitor must not make the stack answer an RTS that is directed
    at a third node: no CTS is sent and nothing is reassembled/delivered."""
    ecu, sent = _make_ecu()
    received = []
    ecu.subscribe(lambda *args: received.append(args))
    try:
        # TP.CM RTS for a 20-byte / 3-packet transfer, destination 0x20,
        # source 0xF9 -> arbitration id 0x18EC20F9.
        ecu.notify(
            0x18EC20F9, [16, 20, 0, 3, 1, 0xB0, 0xFE, 0], time.time()
        )
        time.sleep(0.1)
    finally:
        ecu.stop()

    assert sent == [], "must not answer CTS for an RTS addressed to another node"
    assert received == [], "must not reassemble/deliver a transfer we do not own"


def test_wildcard_observes_address_claim():
    """A wildcard subscriber observes address-claim broadcasts (e.g. to read a
    node's NAME), and the stack transmits nothing in response."""
    ecu, sent = _make_ecu()
    received = []
    ecu.subscribe(
        lambda priority, pgn, sa, timestamp, data: received.append(
            (pgn, sa, list(data))
        )
    )
    try:
        name = [1, 2, 3, 4, 5, 6, 7, 8]
        # Address Claimed: PGN 0xEE00, global destination, source 0xB0
        # -> arbitration id 0x18EEFFB0.
        ecu.notify(0x18EEFFB0, name, time.time())
        time.sleep(0.1)
    finally:
        ecu.stop()

    assert received == [(0xEE00, 0xB0, name)]
    assert sent == [], "observing an address claim must not transmit on the bus"


def test_owned_destination_still_participates():
    """Regression: when a CA owns the destination, the stack still answers the
    RTS/CTS handshake (active participation is preserved)."""
    ecu, sent = _make_ecu()

    class OwnAllCa(j1939.ControllerApplication):
        def message_acceptable(self, dest_address):
            return True

    ca = OwnAllCa(None, None, False)
    ecu.add_ca(controller_application=ca)
    try:
        # Same RTS as above; now the destination is owned, so a CTS must be sent.
        ecu.notify(
            0x18EC20F9, [16, 20, 0, 3, 1, 0xB0, 0xFE, 0], time.time()
        )
        time.sleep(0.1)
    finally:
        ecu.stop()

    assert sent, "an owned destination must still answer the RTS with a CTS"
    # First transmitted frame should be a TP.CM CTS (control byte 17).
    assert sent[0][1][0] == 17, "expected a CTS (control byte 17) response"
