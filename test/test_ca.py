import time

import j1939
from test.helpers.feeder import Feeder


def address_claim(
    feeder,
    arbitrary_address_capable=0,
    expected_state=j1939.ControllerApplication.State.NORMAL
):
    """generic address claim test"""
    name = j1939.Name(
        arbitrary_address_capable=arbitrary_address_capable, 
        industry_group=j1939.Name.IndustryGroup.Industrial,
        vehicle_system_instance=2,
        vehicle_system=127,
        function=201,
        function_instance=16,
        ecu_instance=2,
        manufacturer_code=666,
        identity_number=1234567,
    )
    # create new CA on the bus with given NAME and ADDRESS
    new_ca = feeder.ecu.add_ca(name=name, device_address=128)
    # by starting the CA it announces the given ADDRESS on the bus
    new_ca.start()
    
    # wait until all messages are processed asynchronously
    while len(feeder.can_messages)>0:
        time.sleep(0.500)
    # wait for final processing    
    time.sleep(0.500)

    assert new_ca.state == expected_state


def test_addr_claim_fixed(feeder):
    """Test CA Address claim on the bus with fixed address
    This test runs a "Single Address Capable" claim procedure with a fixed
    address of 128.
    """
    feeder.can_messages = [
        (Feeder.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),    # Address Claimed
    ]

    address_claim(feeder)

def test_addr_claim_fixed_reduced_time(feeder):
    """Test CA Address claim on the bus with fixed address
    This test runs a "Single Address Capable" claim procedure with a fixed
    address of 128. Tests a reduced time between start and first message.
    """
    feeder.can_messages = [
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
        identity_number=1234567,
    )
    new_ca = feeder.ecu.add_ca(name=name, device_address=128)
    new_ca.start(0.2)

    # wait until the address claim message is processed, with a 2s timeout
    deadline = time.monotonic() + 2.0
    while len(feeder.can_messages) > 0 and time.monotonic() < deadline:
        time.sleep(0.050)

    assert len(feeder.can_messages) == 0


def test_addr_claim_fixed_veto_lose(feeder):
    """Test CA Address claim on the bus with fixed address and a veto counterpart
    This test runs a "Single Address Capable" claim procedure with a fixed
    address of 128. A counterpart on the bus declines the address claimed message
    with a veto and we lose our address.
    """
    feeder.can_messages = [
        (Feeder.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),    # Address Claimed
        (Feeder.MsgType.CANRX, 0x18EEFF80, [135, 214, 82, 83, 130, 111, 254, 82], 0.0),    # Veto from Counterpart with lower name
        (Feeder.MsgType.CANTX, 0x18EEFFFE, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),    # CANNOT CLAIM
    ]

    address_claim(feeder, expected_state=j1939.ControllerApplication.State.CANNOT_CLAIM)

def test_addr_claim_fixed_duplicate_response(feeder):
    """Test CA Address claim on the bus and a duplicate response is received from a device with 
    the same name
    """
    feeder.can_messages = [
        (Feeder.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),    # Address Claimed
        (Feeder.MsgType.CANRX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),    # Response from Counterpart with same name
    ]

    address_claim(feeder)


def test_addr_claim_fixed_veto_win(feeder):
    """Test CA Address claim on the bus with fixed address and a veto counterpart
    This test runs a "Single Address Capable" claim procedure with a fixed
    address of 128. A counterpart on the bus declines the address claimed message
    with a veto, but our name is less.
    """
    feeder.can_messages = [
        (Feeder.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),    # Address Claimed
        (Feeder.MsgType.CANRX, 0x18EEFF80, [135, 214, 82, 83, 130, 222, 254, 82], 0.0),    # Veto from Counterpart with higher name
        (Feeder.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),    # resend Address Claimed
    ]

    address_claim(feeder)

def test_addr_claim_arbitrary_veto_lose(feeder):
    """Test CA Address claim on the bus with arbitrary capability a veto counterpart
    This test runs a "Arbitrary Address Capable" claim procedure with an
    address of 128. A counterpart on the bus declines the address claimed message
    with a veto and we lose our address. Our device should claim the next address
    (129) automatically.
    """
    feeder.can_messages = [
        (Feeder.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 210], 0.0),    # Address Claimed 128
        (Feeder.MsgType.CANRX, 0x18EEFF80, [135, 214, 82, 83, 130, 111, 254, 82], 0.0),     # Veto from Counterpart with lower name
        (Feeder.MsgType.CANTX, 0x18EEFF81, [135, 214, 82, 83, 130, 201, 254, 210], 0.0),    # Address Claimed 129
    ]

    address_claim(feeder, arbitrary_address_capable=1)

def test_start_method(feeder):
    """Test CA start method"""
    name = j1939.Name(
        arbitrary_address_capable=0,
        industry_group=j1939.Name.IndustryGroup.Industrial,
        vehicle_system_instance=2,
        vehicle_system=127,
        function=201,
        function_instance=16,
        ecu_instance=2,
        manufacturer_code=666,
        identity_number=1234567,
    )
    # create new CA on the bus with given NAME and ADDRESS
    new_ca = j1939.ControllerApplication(name=name, device_address_preferred=128)
    # by starting the CA it announces the given ADDRESS on the bus
    new_ca.start()
    assert not new_ca.started
    # add ecu to the ca
    new_ca.associate_ecu(feeder.ecu)
    new_ca.start()
    assert new_ca.started

def test_stop_method(feeder):
    """Test CA stop method"""
    name = j1939.Name(
        arbitrary_address_capable=0,
        industry_group=j1939.Name.IndustryGroup.Industrial,
        vehicle_system_instance=2,
        vehicle_system=127,
        function=201,
        function_instance=16,
        ecu_instance=2,
        manufacturer_code=666,
        identity_number=1234567,
    )
    # create new CA on the bus with given NAME and ADDRESS
    new_ca = j1939.ControllerApplication(name=name, device_address_preferred=128)
    # by starting the CA it announces the given ADDRESS on the bus
    new_ca.stop()
    assert not new_ca.started
    # add ecu to the ca

    new_ca.associate_ecu(feeder.ecu)
    new_ca.start()
    assert new_ca.started
    new_ca.stop()
    assert not new_ca.started


def test_bypass_address_claim_with_address_zero(feeder):
    """bypass_address_claim=True with device_address_preferred=0x00 must reach State.NORMAL.

    Address 0x00 (engine controller / ECM) is valid but falsy in Python.
    A truthiness check on the address silently skips the bypass, leaving the
    CA in State.NONE and causing RuntimeError on the first send. Regression
    test for issue #8.
    """
    name = j1939.Name(
        arbitrary_address_capable=0,
        industry_group=j1939.Name.IndustryGroup.Global,
        vehicle_system_instance=0,
        vehicle_system=0,
        function=0,
        function_instance=0,
        ecu_instance=0,
        manufacturer_code=0,
        identity_number=0,
    )
    ca = j1939.ControllerApplication(name=name, device_address_preferred=0x00, bypass_address_claim=True)
    assert ca.state == j1939.ControllerApplication.State.NORMAL
    assert ca.device_address == 0x00


def _commanded_address_name(arbitrary_address_capable=0):
    """NAME used by the Commanded Address tests.

    With arbitrary_address_capable=0 the NAME serializes to
    [135, 214, 82, 83, 130, 201, 254, 82]; with =1 only the most significant
    byte changes (bit 63 set) to 210.
    """
    return j1939.Name(
        arbitrary_address_capable=arbitrary_address_capable,
        industry_group=j1939.Name.IndustryGroup.Industrial,
        vehicle_system_instance=2,
        vehicle_system=127,
        function=201,
        function_instance=16,
        ecu_instance=2,
        manufacturer_code=666,
        identity_number=1234567,
    )


def test_commanded_address_claims_new_address(feeder):
    """A BAM Commanded Address (PGN 65240) whose NAME matches an
    arbitrary-address-capable CA causes that CA to claim the new address.
    The new address (100) is < 128 so it is claimed immediately.
    """
    feeder.can_messages = [
        (Feeder.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 210], 0.0),  # Address Claimed @128
        (Feeder.MsgType.CANRX, 0x1CECFF01, [32, 9, 0, 2, 255, 216, 254, 0], 0.0),          # TP.CM BAM, PGN 65240, 9 bytes, 2 packets
        (Feeder.MsgType.CANRX, 0x1CEBFF01, [1, 135, 214, 82, 83, 130, 201, 254], 0.0),     # TP.DT 1 (NAME bytes 0..6)
        (Feeder.MsgType.CANRX, 0x1CEBFF01, [2, 210, 100, 255, 255, 255, 255, 255], 0.0),   # TP.DT 2 (NAME byte 7 + new SA 100)
        (Feeder.MsgType.CANTX, 0x18EEFF64, [135, 214, 82, 83, 130, 201, 254, 210], 0.0),   # Address Claimed @100
    ]

    name = _commanded_address_name(arbitrary_address_capable=1)
    new_ca = feeder.ecu.add_ca(name=name, device_address=128)
    new_ca.start()

    while len(feeder.can_messages) > 0:
        time.sleep(0.500)
    time.sleep(0.500)

    assert new_ca.state == j1939.ControllerApplication.State.NORMAL
    assert new_ca.device_address == 100


def test_commanded_address_ignored_for_other_name(feeder):
    """A Commanded Address with a NAME that does not match the CA is ignored."""
    feeder.can_messages = [
        (Feeder.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 210], 0.0),  # Address Claimed @128
        (Feeder.MsgType.CANRX, 0x1CECFF01, [32, 9, 0, 2, 255, 216, 254, 0], 0.0),          # TP.CM BAM, PGN 65240
        (Feeder.MsgType.CANRX, 0x1CEBFF01, [1, 136, 214, 82, 83, 130, 201, 254], 0.0),     # TP.DT 1 (NAME byte 0 differs)
        (Feeder.MsgType.CANRX, 0x1CEBFF01, [2, 210, 100, 255, 255, 255, 255, 255], 0.0),   # TP.DT 2
    ]

    name = _commanded_address_name(arbitrary_address_capable=1)
    new_ca = feeder.ecu.add_ca(name=name, device_address=128)
    new_ca.start()

    while len(feeder.can_messages) > 0:
        time.sleep(0.500)
    time.sleep(0.500)

    assert new_ca.device_address == 128


def test_commanded_address_ignored_when_not_arbitrary_capable(feeder):
    """A CA that is not arbitrary-address-capable (default policy) does not
    adopt a matching Commanded Address.
    """
    feeder.can_messages = [
        (Feeder.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 82], 0.0),   # Address Claimed @128
        (Feeder.MsgType.CANRX, 0x1CECFF01, [32, 9, 0, 2, 255, 216, 254, 0], 0.0),          # TP.CM BAM, PGN 65240
        (Feeder.MsgType.CANRX, 0x1CEBFF01, [1, 135, 214, 82, 83, 130, 201, 254], 0.0),     # TP.DT 1
        (Feeder.MsgType.CANRX, 0x1CEBFF01, [2, 82, 100, 255, 255, 255, 255, 255], 0.0),    # TP.DT 2 (matching NAME, new SA 100)
    ]

    name = _commanded_address_name(arbitrary_address_capable=0)
    new_ca = feeder.ecu.add_ca(name=name, device_address=128)
    new_ca.start()

    while len(feeder.can_messages) > 0:
        time.sleep(0.500)
    time.sleep(0.500)

    assert new_ca.device_address == 128


def test_commanded_address_not_delivered_to_subscribers(feeder):
    """Commanded Address is consumed by the CA and not forwarded to generic
    subscribers.
    """
    received_pgns = []

    def on_message(priority, pgn, sa, timestamp, data):
        received_pgns.append(pgn)

    feeder.ecu.subscribe(on_message)

    feeder.can_messages = [
        (Feeder.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 210], 0.0),  # Address Claimed @128
        (Feeder.MsgType.CANRX, 0x1CECFF01, [32, 9, 0, 2, 255, 216, 254, 0], 0.0),          # TP.CM BAM, PGN 65240
        (Feeder.MsgType.CANRX, 0x1CEBFF01, [1, 135, 214, 82, 83, 130, 201, 254], 0.0),     # TP.DT 1
        (Feeder.MsgType.CANRX, 0x1CEBFF01, [2, 210, 100, 255, 255, 255, 255, 255], 0.0),   # TP.DT 2
        (Feeder.MsgType.CANTX, 0x18EEFF64, [135, 214, 82, 83, 130, 201, 254, 210], 0.0),   # Address Claimed @100
    ]

    name = _commanded_address_name(arbitrary_address_capable=1)
    new_ca = feeder.ecu.add_ca(name=name, device_address=128)
    new_ca.start()

    while len(feeder.can_messages) > 0:
        time.sleep(0.500)
    time.sleep(0.500)

    feeder.ecu.unsubscribe(on_message)

    assert j1939.ParameterGroupNumber.PGN.COMMANDED_ADDRESS not in received_pgns


def test_commanded_address_invalid_sa_ignored(feeder):
    """A Commanded Address that commands a non-claimable source address (NULL
    254 / GLOBAL 255) is ignored; the CA keeps its current address and does not
    transmit an Address Claimed for the invalid SA.
    """
    feeder.can_messages = [
        (Feeder.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 210], 0.0),  # Address Claimed @128
        (Feeder.MsgType.CANRX, 0x1CECFF01, [32, 9, 0, 2, 255, 216, 254, 0], 0.0),          # TP.CM BAM, PGN 65240
        (Feeder.MsgType.CANRX, 0x1CEBFF01, [1, 135, 214, 82, 83, 130, 201, 254], 0.0),     # TP.DT 1
        (Feeder.MsgType.CANRX, 0x1CEBFF01, [2, 210, 254, 255, 255, 255, 255, 255], 0.0),   # TP.DT 2 (new SA = NULL 254)
    ]

    name = _commanded_address_name(arbitrary_address_capable=1)
    new_ca = feeder.ecu.add_ca(name=name, device_address=128)
    new_ca.start()

    while len(feeder.can_messages) > 0:
        time.sleep(0.500)
    time.sleep(0.500)

    assert new_ca.state == j1939.ControllerApplication.State.NORMAL
    assert new_ca.device_address == 128


def test_commanded_address_in_veto_range_claims_after_veto(feeder):
    """A Commanded Address for an address in the 128..247 range enters WAIT_VETO
    and resolves to NORMAL at the commanded address. The re-armed veto timeout
    makes the transition happen within the veto window rather than at the next
    periodic claim tick.
    """
    feeder.can_messages = [
        (Feeder.MsgType.CANTX, 0x18EEFF80, [135, 214, 82, 83, 130, 201, 254, 210], 0.0),  # Address Claimed @128
        (Feeder.MsgType.CANRX, 0x1CECFF01, [32, 9, 0, 2, 255, 216, 254, 0], 0.0),          # TP.CM BAM, PGN 65240
        (Feeder.MsgType.CANRX, 0x1CEBFF01, [1, 135, 214, 82, 83, 130, 201, 254], 0.0),     # TP.DT 1
        (Feeder.MsgType.CANRX, 0x1CEBFF01, [2, 210, 200, 255, 255, 255, 255, 255], 0.0),   # TP.DT 2 (new SA = 200)
        (Feeder.MsgType.CANTX, 0x18EEFFC8, [135, 214, 82, 83, 130, 201, 254, 210], 0.0),   # Address Claimed @200
    ]

    name = _commanded_address_name(arbitrary_address_capable=1)
    new_ca = feeder.ecu.add_ca(name=name, device_address=128)
    new_ca.start()

    while len(feeder.can_messages) > 0:
        time.sleep(0.500)
    # allow the (re-armed) veto window to elapse
    time.sleep(0.500)

    assert new_ca.state == j1939.ControllerApplication.State.NORMAL
    assert new_ca.device_address == 200
