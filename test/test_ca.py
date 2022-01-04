import time

import j1939
from feeder import Feeder

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

