import time

import j1939
from test_helpers.feeder import Feeder
from test_helpers.conftest import feeder


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
    new_ca.start(0.25)
    
    # wait until all messages are processed asynchronously 
    # rounded up to account for scheduling delays
    time.sleep(0.3)

    # assert that the expected message was sent
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
