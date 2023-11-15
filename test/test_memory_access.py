import pytest
from test_helpers.feeder import Feeder
from test_helpers.conftest import feeder
import j1939

# fmt: off
read_with_seed_key = [
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x92000007
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0x5A, 0xA5], 0.0),  # DM15 seed response
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0xA5, 0x5A], 0.0),  # DM14 key response
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x01, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    (Feeder.MsgType.CANRX, 0x1CD7F9D4, [0x01, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM16 data transfer
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x19, 0x03, 0x00, 0x00, 0x92, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

read_with_seed_key_busy = [
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x92000007
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0x5A, 0xA5], 0.0),  # DM15 seed response
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0xA5, 0x5A], 0.0),  # DM14 key response
    (Feeder.MsgType.CANRX, 0x18D9F9D4, [0x01, 0x13, 0x03, 0x00, 0x00, 0x91, 0x07, 0x00], 0.0),  # DM14 read address 0x91000007
    (Feeder.MsgType.CANTX, 0x18D8D4F9, [0x00, 0x1B, 0x02, 0x00, 0x00, 0x07, 0xFF, 0xFF], 0.0),  # DM15 Busy Response
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x01, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    (Feeder.MsgType.CANRX, 0x1CD7F9D4, [0x01, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM16 data transfer
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x19, 0x03, 0x00, 0x00, 0x92, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

read_no_seed_key = [
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x92000007
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x01, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    (Feeder.MsgType.CANRX, 0x1CD7F9D4, [0x01, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM16 data transfer
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x19, 0x03, 0x00, 0x00, 0x92, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

write_with_seed_key = [
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x15, 0x07, 0x00, 0x00, 0x91, 0x07, 0x00], 0.0),  # DM14 write address 0x91000007
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0x5A, 0xA5], 0.0),  # DM15 seed response
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x15, 0x07, 0x00, 0x00, 0x91, 0xA5, 0x5A], 0.0),  # DM14 key response
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x01, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    (Feeder.MsgType.CANTX, 0x18D7D4F9, [0x04, 0x44, 0x33, 0x22, 0x11]                  , 0.0),  # DM16 data transfer
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x19, 0x07, 0x00, 0x00, 0x91, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

write_no_seed_key = [
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x15, 0x07, 0x00, 0x00, 0x91, 0x07, 0x00], 0.0),  # DM14 write address 0x91000007
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x01, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    (Feeder.MsgType.CANTX, 0x18D7D4F9, [0x04, 0x44, 0x33, 0x22, 0x11]                  , 0.0),  # DM16 data transfer
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x19, 0x07, 0x00, 0x00, 0x91, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

request_read_with_seed = [
    (Feeder.MsgType.CANTX, 0x18D9F9D4, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # Initialization message used to start listening for DM14 messages
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x91000007
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0x5A, 0xA5], 0.0),  # DM15 seed response
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0xA5, 0x5A], 0.0),  # DM14 key response
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x01, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    (Feeder.MsgType.CANTX, 0x1CD7F9D4, [0x01, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM16 data transfer
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x19, 0x03, 0x00, 0x00, 0x92, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

request_read_no_seed = [
    (Feeder.MsgType.CANTX, 0x18D9F9D4, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # Initialization message used to start listening for DM14 messages
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x91000007
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x01, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    (Feeder.MsgType.CANTX, 0x1CD7F9D4, [0x01, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM16 data transfer
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x19, 0x03, 0x00, 0x00, 0x92, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

request_read_with_seed_busy = [
    (Feeder.MsgType.CANTX, 0x18D9F9D4, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # Initialization message used to start listening for DM14 messages
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x91000007
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0x5A, 0xA5], 0.0),  # DM15 seed response
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x91, 0x07, 0x00], 0.0),  # DM14 read address 0x91000007
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x1B, 0x02, 0x00, 0x00, 0x07, 0xFF, 0xFF], 0.0),  # DM15 Busy Response
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0xA5, 0x5A], 0.0),  # DM14 key response
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x01, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    (Feeder.MsgType.CANTX, 0x1CD7F9D4, [0x01, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM16 data transfer
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x19, 0x03, 0x00, 0x00, 0x92, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

receive_diff_sa_busy = [
    (Feeder.MsgType.CANTX, 0x18D9F9D4, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # Initialization message used to start listening for DM14 messages
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x91000007
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0x5A, 0xA5], 0.0),  # DM15 seed response
    (Feeder.MsgType.CANRX, 0x18D9D4FA, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x91000007
    (Feeder.MsgType.CANTX, 0x18D8FAD4, [0x00, 0x1B, 0x02, 0x00, 0x00, 0x07, 0xFF, 0xFF], 0.0),  # DM15 Busy Response
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0xA5, 0x5A], 0.0),  # DM14 key response
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x01, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    (Feeder.MsgType.CANTX, 0x1CD7F9D4, [0x01, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM16 data transfer
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x19, 0x03, 0x00, 0x00, 0x92, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

request_write_with_seed = [
    (Feeder.MsgType.CANTX, 0x18D9F9D4, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x15, 0x07, 0x00, 0x00, 0x91, 0x07, 0x00], 0.0),  # DM14 write address 0x91000007
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0x5A, 0xA5], 0.0),  # DM15 seed response
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x15, 0x07, 0x00, 0x00, 0x91, 0xA5, 0x5A], 0.0),  # DM14 key response
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x01, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    (Feeder.MsgType.CANRX, 0x18D7D4F9, [0x04, 0x44, 0x33, 0x22, 0x11]                  , 0.0),  # DM16 data transfer
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x19, 0x07, 0x00, 0x00, 0x91, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

request_write_no_seed = [
    (Feeder.MsgType.CANTX, 0x18D9F9D4, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # Random message to start listening for DM14
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x15, 0x07, 0x00, 0x00, 0x91, 0x07, 0x00], 0.0),  # DM14 write address 0x91000007
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x01, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    (Feeder.MsgType.CANRX, 0x18D7D4F9, [0x04, 0x44, 0x33, 0x22, 0x11]                  , 0.0),  # DM16 data transfer
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x19, 0x07, 0x00, 0x00, 0x91, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

error_codes = [0x10, 0x11, 0x12, 0x100, 0x101, 0x1000, 0x1001, 0x100F, 0x10FE]
# fmt: on

flag = False


def key_from_seed(seed):
    return seed ^ 0xFFFF


def generate_seed():
    return 0xA55A


def get_error():
    return [(e.value) for e in j1939.J1939Error]


def global_flag() -> None:
    global flag
    flag = True


def reset_flag() -> None:
    global flag
    flag = False


def teardown():
    reset_flag()


@pytest.mark.parametrize(
    argnames=["expected_messages"],
    argvalues=[[read_with_seed_key], [read_no_seed_key]],
    ids=["With seed key", "Without seed key"],
)
def test_dm14_read(feeder, expected_messages):
    """
    Tests the DM14 read query function
    :param feeder: can message feeder
    :param expected_messages: list of expected messages
    """
    feeder.can_messages = expected_messages
    feeder.pdus_from_messages()

    ca = feeder.accept_all_messages(
        device_address_preferred=0xF9, bypass_address_claim=True
    )

    dm14 = j1939.MemoryAccess(ca)

    if expected_messages == read_with_seed_key:
        dm14.set_seed_key_algorithm(key_from_seed)

    dm14.read(0xD4, 1, 0x92000003, 1)

    feeder.process_messages()


@pytest.mark.parametrize(
    argnames=["expected_messages"],
    argvalues=[[write_with_seed_key], [write_no_seed_key]],
    ids=["With seed key", "Without seed key"],
)
def test_dm14_write(feeder, expected_messages):
    """
    Tests the DM14 write query function
    :param feeder: can message feeder
    :param expected_messages: list of expected messages
    """
    feeder.can_messages = expected_messages
    feeder.pdus_from_messages()

    ca = feeder.accept_all_messages(
        device_address_preferred=0xF9, bypass_address_claim=True
    )

    dm14 = j1939.Dm14Query(ca)
    dm14.set_seed_key_algorithm(key_from_seed)
    values = [0x11223344]
    dm14.write(0xD4, 1, 0x91000007, values, object_byte_size=4)

    feeder.process_messages()


def test_dm14_read_busy(
    feeder,
):
    """
    Tests the DM14 read query response to receiving another request
    :param feeder: can message feeder
    """
    feeder.can_messages = read_with_seed_key_busy
    feeder.pdus_from_messages()

    ca = feeder.accept_all_messages(
        device_address_preferred=0xF9, bypass_address_claim=True
    )

    dm14 = j1939.MemoryAccess(ca)

    dm14.set_seed_key_algorithm(key_from_seed)

    dm14.read(0xD4, 1, 0x92000003, 1)

    feeder.process_messages()


@pytest.mark.parametrize(
    argnames=["expected_messages"],
    argvalues=[[request_read_with_seed], [request_read_no_seed]],
    ids=["With seed key", "Without seed key"],
)
def test_dm14_request_read(feeder, expected_messages):
    """
    Tests the DM14 response to read query function
    :param feeder: can message feeder
    :param expected_messages: list of expected messages
    """
    feeder.can_messages = expected_messages
    feeder.pdus_from_messages()
    ca = feeder.accept_all_messages(
        device_address_preferred=0xD4, bypass_address_claim=True
    )
    ca.send_pgn(
        0,
        (j1939.ParameterGroupNumber.PGN.DM14 >> 8) & 0xFF,
        0xF9 & 0xFF,
        6,
        [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00],
    )
    global flag

    dm14 = j1939.MemoryAccess(ca)
    dm14.set_seed_generator(generate_seed)

    dm14.set_notify(global_flag)

    if expected_messages == request_read_with_seed:
        dm14.set_seed_key_algorithm(key_from_seed)

    while flag is False:
        pass
    reset_flag()
    dm14.respond(True, [0x01], 0xFFFF, 0xFF)

    feeder.process_messages()


def test_dm14_request_read_busy(feeder):
    """
    Tests the DM14 response to read query function while being busy responding to a read query response
    :param feeder: can message feeder
    """
    feeder.can_messages = request_read_with_seed_busy
    feeder.pdus_from_messages()
    ca = feeder.accept_all_messages(
        device_address_preferred=0xD4, bypass_address_claim=True
    )
    ca.send_pgn(
        0,
        (j1939.ParameterGroupNumber.PGN.DM14 >> 8) & 0xFF,
        0xF9 & 0xFF,
        6,
        [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00],
    )
    global flag

    dm14 = j1939.MemoryAccess(ca)
    dm14.set_seed_generator(generate_seed)

    dm14.set_notify(global_flag)

    dm14.set_seed_key_algorithm(key_from_seed)

    while flag is False:
        pass

    reset_flag()
    dm14.respond(True, [0x01], 0xFFFF, 0xFF)

    feeder.process_messages()


def test_dm14_busy_diff_addr(feeder):
    """
    Tests the DM14 response to read query function from different source address while being busy responding to a read query response
    :param feeder: can message feeder
    """
    feeder.can_messages = receive_diff_sa_busy
    feeder.pdus_from_messages()
    ca = feeder.accept_all_messages(
        device_address_preferred=0xD4, bypass_address_claim=True
    )
    ca.send_pgn(
        0,
        (j1939.ParameterGroupNumber.PGN.DM14 >> 8) & 0xFF,
        0xF9 & 0xFF,
        6,
        [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00],
    )
    global flag

    dm14 = j1939.MemoryAccess(ca)
    dm14.set_seed_generator(generate_seed)

    dm14.set_notify(global_flag)

    dm14.set_seed_key_algorithm(key_from_seed)

    while flag is False:
        pass

    reset_flag()
    dm14.respond(True, [0x01], 0xFFFF, 0xFF)

    feeder.process_messages()


@pytest.mark.parametrize(
    argnames=["expected_messages"],
    argvalues=[[request_write_with_seed], [request_write_no_seed]],
    ids=["With seed key", "Without seed key"],
)
def test_dm14_request_write(feeder, expected_messages):
    """
    Tests the DM14 response to write query function
    :param feeder: can message feeder
    :param expected_messages: list of expected messages
    """
    feeder.can_messages = expected_messages
    feeder.pdus_from_messages()
    ca = feeder.accept_all_messages(
        device_address_preferred=0xD4, bypass_address_claim=True
    )
    ca.send_pgn(
        0,
        (j1939.ParameterGroupNumber.PGN.DM14 >> 8) & 0xFF,
        0xF9 & 0xFF,
        6,
        [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00],
    )

    global flag

    dm14 = j1939.MemoryAccess(ca)
    dm14.set_seed_generator(generate_seed)

    dm14.set_notify(global_flag)

    if expected_messages == request_write_with_seed:
        dm14.set_seed_key_algorithm(key_from_seed)
    values = 0x11223344
    while flag is False:
        pass
    reset_flag()
    test = dm14.respond(True, [], 0xFFFF, 0xFF)
    assert values == int.from_bytes(test, byteorder="little", signed=False)

    feeder.process_messages()


@pytest.mark.parametrize(
    "error_code",
    get_error(),
)
def test_dm14_read_error(feeder, error_code):
    """
    Tests that the DM14 read query can react to errors correctly
    :param feeder: can message feeder
    :param error_code: error code to test
    """
    with pytest.raises(RuntimeError) as excinfo:
        feeder.can_messages = [
            (
                Feeder.MsgType.CANTX,
                0x18D9D4F9,
                [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00],
                0.0,
            ),  # DM14 read address 0x92000007
            (
                Feeder.MsgType.CANRX,
                0x18D8F9D4,
                [
                    0x01,
                    0x1B,
                    (error_code & 0xFF),
                    ((error_code >> 8) & 0xFF),
                    (error_code >> 16),
                    0x07,
                    0xFF,
                    0xFF,
                ],
                0.0,
            ),  # DM15 proceed response
        ]

        feeder.pdus_from_messages()

        ca = feeder.accept_all_messages(
            device_address_preferred=0xF9, bypass_address_claim=True
        )

        dm14 = j1939.MemoryAccess(ca)

        dm14.read(0xD4, 1, 0x92000003, 1)

        feeder.process_messages()
    assert j1939.ErrorInfo[error_code] in str(excinfo.value)

    feeder.process_messages()


def test_dm14_read_unknown_error(feeder):
    """
    Tests that the DM14 read query can react to unknown errors correctly
    :param feeder: can message feeder
    """
    with pytest.raises(RuntimeError) as excinfo:
        feeder.can_messages = [
            (
                Feeder.MsgType.CANTX,
                0x18D9D4F9,
                [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00],
                0.0,
            ),  # DM14 read address 0x92000007
            (
                Feeder.MsgType.CANRX,
                0x18D8F9D4,
                [
                    0x01,
                    0x1B,
                    (0xBEEF & 0xFF),
                    ((0xBEEF >> 8) & 0xFF),
                    (0xBEEF >> 16),
                    0x07,
                    0xFF,
                    0xFF,
                ],
                0.0,
            ),  # DM15 proceed response
        ]

        feeder.pdus_from_messages()

        ca = feeder.accept_all_messages(
            device_address_preferred=0xF9, bypass_address_claim=True
        )

        dm14 = j1939.MemoryAccess(ca)

        dm14.read(0xD4, 1, 0x92000003, 1)

        feeder.process_messages()
    assert str(hex(0xBEEF)) in str(excinfo.value)

    feeder.process_messages()


@pytest.mark.parametrize(
    "error_code",
    get_error(),
)
def test_dm14_write_error(feeder, error_code):
    """
    Tests that the DM14 write query can react to errors correctly
    :param feeder: can message feeder
    :param error_code: error code to test
    """
    with pytest.raises(RuntimeError) as excinfo:
        feeder.can_messages = [
            (
                Feeder.MsgType.CANTX,
                0x18D9D4F9,
                [0x01, 0x15, 0x07, 0x00, 0x00, 0x91, 0x07, 0x00],
                0.0,
            ),  # DM14 write address 0x91000007
            (
                Feeder.MsgType.CANRX,
                0x18D8F9D4,
                [
                    0x01,
                    0x1B,
                    (error_code & 0xFF),
                    ((error_code >> 8) & 0xFF),
                    (error_code >> 16),
                    0x07,
                    0xFF,
                    0xFF,
                ],
                0.0,
            ),  # DM15 proceed response
        ]

        feeder.pdus_from_messages()

        ca = feeder.accept_all_messages(
            device_address_preferred=0xF9, bypass_address_claim=True
        )

        dm14 = j1939.Dm14Query(ca)
        dm14.set_seed_key_algorithm(key_from_seed)
        values = [0x11223344]
        dm14.write(0xD4, 1, 0x91000007, values, object_byte_size=4)

    assert j1939.ErrorInfo[error_code] in str(excinfo.value)

    feeder.process_messages()


# TODO: moar test
