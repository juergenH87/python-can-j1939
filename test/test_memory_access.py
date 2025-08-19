import pytest
from test_helpers.feeder import Feeder
from test_helpers.conftest import feeder
import queue
import j1939

# fmt: off
read_with_seed_key = [
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x92000003
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0x5A, 0xA5], 0.0),  # DM15 seed response
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0xA5, 0x5A], 0.0),  # DM14 key response
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x01, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    (Feeder.MsgType.CANRX, 0x1CD7F9D4, [0x01, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM16 data transfer
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x19, 0x03, 0x00, 0x00, 0x92, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

read_with_seed_key_busy = [
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x92000003
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0x5A, 0xA5], 0.0),  # DM15 seed response
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0xA5, 0x5A], 0.0),  # DM14 key response
    (Feeder.MsgType.CANRX, 0x18D9F9D4, [0x01, 0x13, 0x03, 0x00, 0x00, 0x91, 0x07, 0x00], 0.0),  # DM14 read address 0x91000003
    (Feeder.MsgType.CANTX, 0x18D8D4F9, [0x00, 0x1B, 0x02, 0x00, 0x00, 0x07, 0xFF, 0xFF], 0.0),  # DM15 Busy Response
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x01, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    (Feeder.MsgType.CANRX, 0x1CD7F9D4, [0x01, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM16 data transfer
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x19, 0x03, 0x00, 0x00, 0x92, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

read_no_seed_key = [
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x92000003
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x01, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    (Feeder.MsgType.CANRX, 0x1CD7F9D4, [0x01, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM16 data transfer
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x19, 0x03, 0x00, 0x00, 0x92, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

read_no_seed_key_8_bytes = [
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x08, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x92000003
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x08, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    # DM16 data transfer using Transport Protocol, start
    (Feeder.MsgType.CANRX, 0x18ECF9D4, [0x10, 0x09, 0x00, 0x02, 0x02, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_RTS, size=9, packets=2, maxPackets=2, PGN=D700
    (Feeder.MsgType.CANTX, 0x1CECD4F9, [0x11, 0x02, 0x01, 0xFF, 0xFF, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_CTS, packets=2, nextPacketNum=1, PGN=D700
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x01] + [0xFF] + [0xAB] * 6                    , 0.0),  # TP.DT, 1, DM16 part 1, FF + data 1-6
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x02] + [0xAB] * 2 + [0xFF] * 5                , 0.0),  # TP.DT, 2, DM16 part 2, data 7-8
    (Feeder.MsgType.CANTX, 0x1CECD4F9, [0x13, 0x09, 0x00, 0x02, 0xFF, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_EndOfMsgACK, size=9, packets=2, PGN=D700
    # DM16 data transfer using Transport Protocol, end
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x19, 0x03, 0x00, 0x00, 0x92, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

read_no_seed_key_256_bytes = [
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x00, 0x33, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x92000003
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x31, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    # DM16 data transfer using Transport Protocol, start
    (Feeder.MsgType.CANRX, 0x18ECF9D4, [0x10, 0x01, 0x01, 0x25, 0x25, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_RTS, size=257, packets=37, maxPackets=37, PGN=D700
    (Feeder.MsgType.CANTX, 0x1CECD4F9, [0x11, 0x25, 0x01, 0xFF, 0xFF, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_CTS, packets=37, nextPacketNum=1, PGN=D700
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x01] + [0xFF] + [0xAB] * 6                    , 0.0),  # TP.DT, 1, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x02] + [0xAB] * 7                             , 0.0),  # TP.DT, 2, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x03] + [0xAB] * 7                             , 0.0),  # TP.DT, 3, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x04] + [0xAB] * 7                             , 0.0),  # TP.DT, 4, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x05] + [0xAB] * 7                             , 0.0),  # TP.DT, 5, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x06] + [0xAB] * 7                             , 0.0),  # TP.DT, 6, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x07] + [0xAB] * 7                             , 0.0),  # TP.DT, 7, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x08] + [0xAB] * 7                             , 0.0),  # TP.DT, 8, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x09] + [0xAB] * 7                             , 0.0),  # TP.DT, 9, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x0A] + [0xAB] * 7                             , 0.0),  # TP.DT, 10, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x0B] + [0xAB] * 7                             , 0.0),  # TP.DT, 11, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x0C] + [0xAB] * 7                             , 0.0),  # TP.DT, 12, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x0D] + [0xAB] * 7                             , 0.0),  # TP.DT, 13, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x0E] + [0xAB] * 7                             , 0.0),  # TP.DT, 14, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x0F] + [0xAB] * 7                             , 0.0),  # TP.DT, 15, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x10] + [0xAB] * 7                             , 0.0),  # TP.DT, 16, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x11] + [0xAB] * 7                             , 0.0),  # TP.DT, 17, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x12] + [0xAB] * 7                             , 0.0),  # TP.DT, 18, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x13] + [0xAB] * 7                             , 0.0),  # TP.DT, 19, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x14] + [0xAB] * 7                             , 0.0),  # TP.DT, 20, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x15] + [0xAB] * 7                             , 0.0),  # TP.DT, 21, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x16] + [0xAB] * 7                             , 0.0),  # TP.DT, 22, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x17] + [0xAB] * 7                             , 0.0),  # TP.DT, 23, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x18] + [0xAB] * 7                             , 0.0),  # TP.DT, 24, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x19] + [0xAB] * 7                             , 0.0),  # TP.DT, 25, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x1A] + [0xAB] * 7                             , 0.0),  # TP.DT, 26, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x1B] + [0xAB] * 7                             , 0.0),  # TP.DT, 27, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x1C] + [0xAB] * 7                             , 0.0),  # TP.DT, 28, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x1D] + [0xAB] * 7                             , 0.0),  # TP.DT, 29, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x1E] + [0xAB] * 7                             , 0.0),  # TP.DT, 30, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x1F] + [0xAB] * 7                             , 0.0),  # TP.DT, 31, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x20] + [0xAB] * 7                             , 0.0),  # TP.DT, 32, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x21] + [0xAB] * 7                             , 0.0),  # TP.DT, 33, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x22] + [0xAB] * 7                             , 0.0),  # TP.DT, 34, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x23] + [0xAB] * 7                             , 0.0),  # TP.DT, 35, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x24] + [0xAB] * 7                             , 0.0),  # TP.DT, 36, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBF9D4, [0x25] + [0xAB] * 5 + [0xFF] * 2                , 0.0),  # TP.DT, 37, DM16 data
    (Feeder.MsgType.CANTX, 0x1CECD4F9, [0x13, 0x01, 0x01, 0x25, 0xFF, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_EndOfMsgACK, size=257, packets=37, PGN=D700
    # DM16 data transfer using Transport Protocol, end
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

write_no_seed_key_8_bytes_data = [
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x08, 0x15, 0x07, 0x00, 0x00, 0x91, 0x07, 0x00], 0.0),  # DM14 write address 0x91000007
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x08, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    # DM16 data transfer using Transport Protocol, start
    (Feeder.MsgType.CANTX, 0x18ECD4F9, [0x10, 0x09, 0x00, 0x02, 0x02, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_RTS, size=9, packets=2, maxPackets=255, PGN=D700
    (Feeder.MsgType.CANRX, 0x18ECF9D4, [0x11, 0x02, 0x01, 0xFF, 0xFF, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_CTS, packets=2, nextPacketNum=1, PGN=D700
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x01] + [0xFF] + [0xAB] * 6                    , 0.0),  # TP.DT, 1, DM16 part 1, FF + data 1-6
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x02] + [0xAB] * 2 + [0xFF] * 5                , 0.0),  # TP.DT, 2, DM16 part 2, data 7-8
    (Feeder.MsgType.CANRX, 0x18ECF9D4, [0x13, 0x09, 0x00, 0x02, 0xFF, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_EndOfMsgACK, size=9, packets=2, PGN=D700
    # DM16 data transfer using Transport Protocol, end
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x19, 0x07, 0x00, 0x00, 0x91, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

write_no_seed_key_256_bytes_data = [
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x00, 0x35, 0x07, 0x00, 0x00, 0x91, 0x07, 0x00], 0.0),  # DM14 write address 0x91000007
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x31, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    # DM16 data transfer using Transport Protocol, start
    (Feeder.MsgType.CANTX, 0x18ECD4F9, [0x10, 0x01, 0x01, 0x25, 0x25, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_RTS, size=257, packets=37, maxPackets=37, PGN=D700
    (Feeder.MsgType.CANRX, 0x18ECF9D4, [0x11, 0x25, 0x01, 0xFF, 0xFF, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_CTS, packets=37, nextPacketNum=1, PGN=D700
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x01] + [0xFF] + [0xAB] * 6                    , 0.0),  # TP.DT, 1, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x02] + [0xAB] * 7                             , 0.0),  # TP.DT, 2, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x03] + [0xAB] * 7                             , 0.0),  # TP.DT, 3, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x04] + [0xAB] * 7                             , 0.0),  # TP.DT, 4, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x05] + [0xAB] * 7                             , 0.0),  # TP.DT, 5, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x06] + [0xAB] * 7                             , 0.0),  # TP.DT, 6, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x07] + [0xAB] * 7                             , 0.0),  # TP.DT, 7, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x08] + [0xAB] * 7                             , 0.0),  # TP.DT, 8, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x09] + [0xAB] * 7                             , 0.0),  # TP.DT, 9, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x0A] + [0xAB] * 7                             , 0.0),  # TP.DT, 10, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x0B] + [0xAB] * 7                             , 0.0),  # TP.DT, 11, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x0C] + [0xAB] * 7                             , 0.0),  # TP.DT, 12, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x0D] + [0xAB] * 7                             , 0.0),  # TP.DT, 13, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x0E] + [0xAB] * 7                             , 0.0),  # TP.DT, 14, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x0F] + [0xAB] * 7                             , 0.0),  # TP.DT, 15, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x10] + [0xAB] * 7                             , 0.0),  # TP.DT, 16, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x11] + [0xAB] * 7                             , 0.0),  # TP.DT, 17, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x12] + [0xAB] * 7                             , 0.0),  # TP.DT, 18, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x13] + [0xAB] * 7                             , 0.0),  # TP.DT, 19, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x14] + [0xAB] * 7                             , 0.0),  # TP.DT, 20, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x15] + [0xAB] * 7                             , 0.0),  # TP.DT, 21, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x16] + [0xAB] * 7                             , 0.0),  # TP.DT, 22, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x17] + [0xAB] * 7                             , 0.0),  # TP.DT, 23, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x18] + [0xAB] * 7                             , 0.0),  # TP.DT, 24, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x19] + [0xAB] * 7                             , 0.0),  # TP.DT, 25, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x1A] + [0xAB] * 7                             , 0.0),  # TP.DT, 26, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x1B] + [0xAB] * 7                             , 0.0),  # TP.DT, 27, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x1C] + [0xAB] * 7                             , 0.0),  # TP.DT, 28, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x1D] + [0xAB] * 7                             , 0.0),  # TP.DT, 29, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x1E] + [0xAB] * 7                             , 0.0),  # TP.DT, 30, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x1F] + [0xAB] * 7                             , 0.0),  # TP.DT, 31, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x20] + [0xAB] * 7                             , 0.0),  # TP.DT, 32, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x21] + [0xAB] * 7                             , 0.0),  # TP.DT, 33, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x22] + [0xAB] * 7                             , 0.0),  # TP.DT, 34, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x23] + [0xAB] * 7                             , 0.0),  # TP.DT, 35, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x24] + [0xAB] * 7                             , 0.0),  # TP.DT, 36, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBD4F9, [0x25] + [0xAB] * 5 + [0xFF] * 2                , 0.0),  # TP.DT, 37, DM16 data
    (Feeder.MsgType.CANRX, 0x18ECF9D4, [0x13, 0x01, 0x01, 0x25, 0xFF, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_EndOfMsgACK, size=257, packets=37, PGN=D700
    # DM16 data transfer using Transport Protocol, end
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

request_read_no_seed_8_bytes = [
    (Feeder.MsgType.CANTX, 0x18D9F9D4, [0x08, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # Initialization message used to start listening for DM14 messages
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x08, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x92000003
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x08, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    # DM16 data transfer using Transport Protocol, start
    (Feeder.MsgType.CANTX, 0x1CECF9D4, [0x10, 0x09, 0x00, 0x02, 0x02, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_RTS, size=9, packets=2, maxPackets=2, PGN=D700
    (Feeder.MsgType.CANRX, 0x18ECD4F9, [0x11, 0x02, 0x01, 0xFF, 0xFF, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_CTS, packets=2, nextPacketNum=1, PGN=D700
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x01] + [0xFF] + [0xAB] * 6                    , 0.0),  # TP.DT, 1, DM16 part 1, FF + data 1-6
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x02] + [0xAB] * 2 + [0xFF] * 5                , 0.0),  # TP.DT, 2, DM16 part 2, data 7-8
    (Feeder.MsgType.CANRX, 0x18ECD4F9, [0x13, 0x09, 0x00, 0x02, 0xFF, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_EndOfMsgACK, size=9, packets=2, PGN=D700
    # DM16 data transfer using Transport Protocol, end
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x19, 0x03, 0x00, 0x00, 0x92, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

request_read_no_seed_256_bytes = [
    (Feeder.MsgType.CANTX, 0x18D9F9D4, [0x00, 0x33, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # Initialization message used to start listening for DM14 messages
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x00, 0x33, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x92000003
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x31, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    # DM16 data transfer using Transport Protocol, start
    (Feeder.MsgType.CANTX, 0x1CECF9D4, [0x10, 0x01, 0x01, 0x25, 0x25, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_RTS, size=257, packets=37, maxPackets=37, PGN=D700
    (Feeder.MsgType.CANRX, 0x18ECD4F9, [0x11, 0x25, 0x01, 0xFF, 0xFF, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_CTS, packets=37, nextPacketNum=1, PGN=D700
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x01] + [0xFF] + [0xAB] * 6                    , 0.0),  # TP.DT, 1, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x02] + [0xAB] * 7                             , 0.0),  # TP.DT, 2, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x03] + [0xAB] * 7                             , 0.0),  # TP.DT, 3, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x04] + [0xAB] * 7                             , 0.0),  # TP.DT, 4, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x05] + [0xAB] * 7                             , 0.0),  # TP.DT, 5, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x06] + [0xAB] * 7                             , 0.0),  # TP.DT, 6, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x07] + [0xAB] * 7                             , 0.0),  # TP.DT, 7, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x08] + [0xAB] * 7                             , 0.0),  # TP.DT, 8, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x09] + [0xAB] * 7                             , 0.0),  # TP.DT, 9, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x0A] + [0xAB] * 7                             , 0.0),  # TP.DT, 10, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x0B] + [0xAB] * 7                             , 0.0),  # TP.DT, 11, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x0C] + [0xAB] * 7                             , 0.0),  # TP.DT, 12, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x0D] + [0xAB] * 7                             , 0.0),  # TP.DT, 13, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x0E] + [0xAB] * 7                             , 0.0),  # TP.DT, 14, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x0F] + [0xAB] * 7                             , 0.0),  # TP.DT, 15, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x10] + [0xAB] * 7                             , 0.0),  # TP.DT, 16, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x11] + [0xAB] * 7                             , 0.0),  # TP.DT, 17, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x12] + [0xAB] * 7                             , 0.0),  # TP.DT, 18, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x13] + [0xAB] * 7                             , 0.0),  # TP.DT, 19, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x14] + [0xAB] * 7                             , 0.0),  # TP.DT, 20, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x15] + [0xAB] * 7                             , 0.0),  # TP.DT, 21, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x16] + [0xAB] * 7                             , 0.0),  # TP.DT, 22, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x17] + [0xAB] * 7                             , 0.0),  # TP.DT, 23, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x18] + [0xAB] * 7                             , 0.0),  # TP.DT, 24, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x19] + [0xAB] * 7                             , 0.0),  # TP.DT, 25, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x1A] + [0xAB] * 7                             , 0.0),  # TP.DT, 26, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x1B] + [0xAB] * 7                             , 0.0),  # TP.DT, 27, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x1C] + [0xAB] * 7                             , 0.0),  # TP.DT, 28, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x1D] + [0xAB] * 7                             , 0.0),  # TP.DT, 29, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x1E] + [0xAB] * 7                             , 0.0),  # TP.DT, 30, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x1F] + [0xAB] * 7                             , 0.0),  # TP.DT, 31, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x20] + [0xAB] * 7                             , 0.0),  # TP.DT, 32, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x21] + [0xAB] * 7                             , 0.0),  # TP.DT, 33, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x22] + [0xAB] * 7                             , 0.0),  # TP.DT, 34, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x23] + [0xAB] * 7                             , 0.0),  # TP.DT, 35, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x24] + [0xAB] * 7                             , 0.0),  # TP.DT, 36, DM16 data
    (Feeder.MsgType.CANTX, 0x1CEBF9D4, [0x25] + [0xAB] * 5 + [0xFF] * 2                , 0.0),  # TP.DT, 37, DM16 data
    (Feeder.MsgType.CANRX, 0x18ECD4F9, [0x13, 0x01, 0x01, 0x25, 0xFF, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_EndOfMsgACK, size=257, packets=37, PGN=D700
    # DM16 data transfer using Transport Protocol, end
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x19, 0x03, 0x00, 0x00, 0x92, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

request_read_with_seed_busy = [
    (Feeder.MsgType.CANTX, 0x18D9F9D4, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # Initialization message used to start listening for DM14 messages
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x92000003
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0x5A, 0xA5], 0.0),  # DM15 seed response
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x91, 0x07, 0x00], 0.0),  # DM14 read address 0x91000003
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x1B, 0x02, 0x00, 0x00, 0x07, 0xFF, 0xFF], 0.0),  # DM15 Busy Response
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0xA5, 0x5A], 0.0),  # DM14 key response
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x01, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    (Feeder.MsgType.CANTX, 0x1CD7F9D4, [0x01, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM16 data transfer
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x19, 0x03, 0x00, 0x00, 0x92, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

receive_diff_sa_busy = [
    (Feeder.MsgType.CANTX, 0x18D9F9D4, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # Initialization message used to start listening for DM14 messages
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x92000003
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0x5A, 0xA5], 0.0),  # DM15 seed response
    (Feeder.MsgType.CANRX, 0x18D9D4FA, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x92000003
    (Feeder.MsgType.CANTX, 0x18D8FAD4, [0x00, 0x1B, 0x02, 0x00, 0x00, 0x07, 0xFF, 0xFF], 0.0),  # DM15 Busy Response
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0xA5, 0x5A], 0.0),  # DM14 key response
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x01, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    (Feeder.MsgType.CANTX, 0x1CD7F9D4, [0x01, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM16 data transfer
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x19, 0x03, 0x00, 0x00, 0x92, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

request_write_with_seed = [
    (Feeder.MsgType.CANTX, 0x18D9F9D4, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # Random message to start listening for DM14
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

request_write_no_seed_8_bytes = [
    (Feeder.MsgType.CANTX, 0x18D9F9D4, [0x08, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # Random message to start listening for DM14
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x08, 0x15, 0x07, 0x00, 0x00, 0x91, 0x07, 0x00], 0.0),  # DM14 write address 0x91000007
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x08, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    # DM16 data transfer using Transport Protocol, start
    (Feeder.MsgType.CANRX, 0x18ECD4F9, [0x10, 0x09, 0x00, 0x02, 0x02, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_RTS, size=9, packets=2, maxPackets=2, PGN=D700
    (Feeder.MsgType.CANTX, 0x1CECF9D4, [0x11, 0x02, 0x01, 0xFF, 0xFF, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_CTS, packets=2, nextPacketNum=1, PGN=D700
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x01] + [0xFF] + [0xAB] * 6                    , 0.0),  # TP.DT, 1, DM16 part 1, FF + data 1-6
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x02] + [0xAB] * 2 + [0xFF] * 5                , 0.0),  # TP.DT, 2, DM16 part 2, data 7-8
    (Feeder.MsgType.CANTX, 0x1CECF9D4, [0x13, 0x09, 0x00, 0x02, 0xFF, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_EndOfMsgACK, size=9, packets=2, PGN=D700
    # DM16 data transfer using Transport Protocol, end
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x19, 0x07, 0x00, 0x00, 0x91, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

request_write_no_seed_256_bytes = [
    (Feeder.MsgType.CANTX, 0x18D9F9D4, [0x00, 0x33, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # Random message to start listening for DM14
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x00, 0x35, 0x07, 0x00, 0x00, 0x91, 0x07, 0x00], 0.0),  # DM14 write address 0x91000007
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x31, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
    # DM16 data transfer using Transport Protocol, start
    (Feeder.MsgType.CANRX, 0x18ECD4F9, [0x10, 0x01, 0x01, 0x25, 0x25, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_RTS, size=257, packets=37, maxPackets=37, PGN=D700
    (Feeder.MsgType.CANTX, 0x1CECF9D4, [0x11, 0x25, 0x01, 0xFF, 0xFF, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_CTS, packets=37, nextPacketNum=1, PGN=D700
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x01] + [0xFF] + [0xAB] * 6                    , 0.0),  # TP.DT, 1, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x02] + [0xAB] * 7                             , 0.0),  # TP.DT, 2, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x03] + [0xAB] * 7                             , 0.0),  # TP.DT, 3, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x04] + [0xAB] * 7                             , 0.0),  # TP.DT, 4, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x05] + [0xAB] * 7                             , 0.0),  # TP.DT, 5, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x06] + [0xAB] * 7                             , 0.0),  # TP.DT, 6, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x07] + [0xAB] * 7                             , 0.0),  # TP.DT, 7, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x08] + [0xAB] * 7                             , 0.0),  # TP.DT, 8, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x09] + [0xAB] * 7                             , 0.0),  # TP.DT, 9, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x0A] + [0xAB] * 7                             , 0.0),  # TP.DT, 10, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x0B] + [0xAB] * 7                             , 0.0),  # TP.DT, 11, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x0C] + [0xAB] * 7                             , 0.0),  # TP.DT, 12, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x0D] + [0xAB] * 7                             , 0.0),  # TP.DT, 13, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x0E] + [0xAB] * 7                             , 0.0),  # TP.DT, 14, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x0F] + [0xAB] * 7                             , 0.0),  # TP.DT, 15, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x10] + [0xAB] * 7                             , 0.0),  # TP.DT, 16, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x11] + [0xAB] * 7                             , 0.0),  # TP.DT, 17, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x12] + [0xAB] * 7                             , 0.0),  # TP.DT, 18, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x13] + [0xAB] * 7                             , 0.0),  # TP.DT, 19, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x14] + [0xAB] * 7                             , 0.0),  # TP.DT, 20, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x15] + [0xAB] * 7                             , 0.0),  # TP.DT, 21, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x16] + [0xAB] * 7                             , 0.0),  # TP.DT, 22, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x17] + [0xAB] * 7                             , 0.0),  # TP.DT, 23, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x18] + [0xAB] * 7                             , 0.0),  # TP.DT, 24, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x19] + [0xAB] * 7                             , 0.0),  # TP.DT, 25, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x1A] + [0xAB] * 7                             , 0.0),  # TP.DT, 26, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x1B] + [0xAB] * 7                             , 0.0),  # TP.DT, 27, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x1C] + [0xAB] * 7                             , 0.0),  # TP.DT, 28, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x1D] + [0xAB] * 7                             , 0.0),  # TP.DT, 29, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x1E] + [0xAB] * 7                             , 0.0),  # TP.DT, 30, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x1F] + [0xAB] * 7                             , 0.0),  # TP.DT, 31, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x20] + [0xAB] * 7                             , 0.0),  # TP.DT, 32, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x21] + [0xAB] * 7                             , 0.0),  # TP.DT, 33, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x22] + [0xAB] * 7                             , 0.0),  # TP.DT, 34, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x23] + [0xAB] * 7                             , 0.0),  # TP.DT, 35, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x24] + [0xAB] * 7                             , 0.0),  # TP.DT, 36, DM16 data
    (Feeder.MsgType.CANRX, 0x18EBD4F9, [0x25] + [0xAB] * 5 + [0xFF] * 2                , 0.0),  # TP.DT, 37, DM16 data
    (Feeder.MsgType.CANTX, 0x1CECF9D4, [0x13, 0x01, 0x01, 0x25, 0xFF, 0x00, 0xD7, 0x00], 0.0),  # TP.CM_EndOfMsgACK, size=257, packets=37, PGN=D700
    # DM16 data transfer using Transport Protocol, end
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x00, 0x19, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 operation completed
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x19, 0x07, 0x00, 0x00, 0x91, 0xFF, 0xFF], 0.0),  # DM14 operation completed
]

request_write_no_seed_timeout = [
    (Feeder.MsgType.CANTX, 0x18D9F9D4, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # Random message to start listening for DM14
    (Feeder.MsgType.CANRX, 0x18D9D4F9, [0x01, 0x15, 0x07, 0x00, 0x00, 0x91, 0x07, 0x00], 0.0),  # DM14 write address 0x91000007
    (Feeder.MsgType.CANTX, 0x18D8F9D4, [0x01, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], 0.0),  # DM15 proceed response
]

read_with_seed_error = [
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x92000003
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0x5A, 0xA5], 0.0),  # DM15 seed response
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0xA5, 0x5A], 0.0),  # DM14 key response
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x1B, 0x01, 0x00, 0x00, 0x07, 0xFF, 0xFF], 0.0),  # DM15 error response
]

read_no_seed_error = [
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00], 0.0),  # DM14 read address 0x92000003
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x1B, 0x01, 0x00, 0x00, 0x07, 0xFF, 0xFF], 0.0),  # DM15 error response
]

write_with_seed_error = [
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x15, 0x07, 0x00, 0x00, 0x91, 0x07, 0x00], 0.0),  # DM14 write address 0x91000007
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x11, 0xFF, 0xFF, 0xFF, 0xFF, 0x5A, 0xA5], 0.0),  # DM15 seed response
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x15, 0x07, 0x00, 0x00, 0x91, 0xA5, 0x5A], 0.0),  # DM14 key response
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x1B, 0x01, 0x00, 0x00, 0x07, 0xFF, 0xFF], 0.0),  # DM15 error response
]

write_no_seed_error = [
    (Feeder.MsgType.CANTX, 0x18D9D4F9, [0x01, 0x15, 0x07, 0x00, 0x00, 0x91, 0x07, 0x00], 0.0),  # DM14 write address 0x91000007
    (Feeder.MsgType.CANRX, 0x18D8F9D4, [0x00, 0x1B, 0x01, 0x00, 0x00, 0x07, 0xFF, 0xFF], 0.0),  # DM15 error response
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


def proceed(
    command: int,
    address: int,
    pointer_type: int,
    length: int,
    object_count: int,
    key: int,
    source_addr: int,
    access_level: int,
    seed: int,
) -> bool:
    """
    Determines whether to proceed with the DM14 request
    :param command: DM14 command
    :param address: DM14 address
    :param pointer_type: DM14 pointer type
    :param length: DM14 length
    :param object_count: number of objects to read
    :param key: key
    :param source_addr: DM14 source address of message requesting access
    :param access_level: DM14 access level
    :param seed: DM14 seed
    """
    return True


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
    argvalues=[[read_no_seed_key_8_bytes], [read_no_seed_key_256_bytes]],
    ids=["Without seed key 8 bytes", "Without seed key 256 bytes"],
)
def test_dm14_read_large_data(feeder, expected_messages):
    """
    Tests the DM14 read query function with large data packet in range (8-255 bytes) and in range (256-1784 bytes)
    :param feeder: can message feeder
    :param expected_messages: list of expected messages
    """
    if expected_messages == read_no_seed_key_8_bytes:
        num_of_bytes = 8
    elif expected_messages == read_no_seed_key_256_bytes:
        num_of_bytes = 256
    else:
        assert False

    feeder.can_messages = expected_messages
    feeder.pdus_from_messages()

    ca = feeder.accept_all_messages(
        device_address_preferred=0xF9, bypass_address_claim=True
    )

    dm14 = j1939.MemoryAccess(ca)

    values = dm14.read(0xD4, 1, 0x92000003, num_of_bytes)
    assert values == [0xAB] * num_of_bytes

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


@pytest.mark.parametrize(
    argnames=["expected_messages"],
    argvalues=[[write_no_seed_key_8_bytes_data], [write_no_seed_key_256_bytes_data]],
    ids=["Without seed key 8 bytes", "Without seed key 256 bytes"],
)
def test_dm14_write_large_data(feeder, expected_messages):
    """
    Tests the DM14 write query function with large data packet in range (8-255 bytes) and in range (256-1784 bytes)
    :param feeder: can message feeder
    :param expected_messages: list of expected messages
    """
    if expected_messages == write_no_seed_key_8_bytes_data:
        num_of_bytes = 8
    elif expected_messages == write_no_seed_key_256_bytes_data:
        num_of_bytes = 256
    else:
        assert False

    feeder.can_messages = expected_messages
    feeder.pdus_from_messages()

    ca = feeder.accept_all_messages(
        device_address_preferred=0xF9, bypass_address_claim=True
    )

    dm14 = j1939.Dm14Query(ca)
    values = [0xAB]*num_of_bytes
    dm14.write(0xD4, 1, 0x91000007, values, object_byte_size=1)

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
    dm14.set_proceed(proceed)
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

    dm14 = j1939.MemoryAccess(ca)
    dm14.set_seed_generator(generate_seed)
    dm14.set_proceed(proceed)
    dm14.set_notify(global_flag)

    if expected_messages == request_read_with_seed:
        dm14.set_seed_key_algorithm(key_from_seed)

    ca.send_pgn(
        0,
        (j1939.ParameterGroupNumber.PGN.DM14 >> 8) & 0xFF,
        0xF9 & 0xFF,
        6,
        [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00],
    )

    global flag
    while flag is False:
        pass

    reset_flag()
    dm14.respond(True, [0x01], 0xFFFF, 0xFF)

    feeder.process_messages()


@pytest.mark.parametrize(
    argnames=["expected_messages"],
    argvalues=[[request_read_no_seed_8_bytes], [request_read_no_seed_256_bytes]],
    ids=["Without seed key 8 bytes", "Without seed key 256 bytes"],
)
def test_dm14_request_read_large_data(feeder, expected_messages):
    """
    Tests the DM14 response to read query function with large data packet in range (8-255 bytes) and in range (256-1784 bytes)
    :param feeder: can message feeder
    :param expected_messages: list of expected messages
    """
    if expected_messages == request_read_no_seed_8_bytes:
        num_data_bytes = 8
    elif expected_messages == request_read_no_seed_256_bytes:
        num_data_bytes = 256
    else:
        assert False

    feeder.can_messages = expected_messages
    feeder.pdus_from_messages()
    ca = feeder.accept_all_messages(
        device_address_preferred=0xD4, bypass_address_claim=True
    )

    dm14 = j1939.MemoryAccess(ca)
    dm14.set_proceed(proceed)
    dm14.set_notify(global_flag)

    ca.send_pgn(
        0,
        (j1939.ParameterGroupNumber.PGN.DM14 >> 8) & 0xFF,
        0xF9 & 0xFF,
        6,
        [num_data_bytes & 0xFF, ((num_data_bytes & 0x300) >> 3) + 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00],
    )

    global flag
    while flag is False:
        pass

    reset_flag()
    dm14.respond(True, [0xAB] * num_data_bytes, 0xFFFF, 0xFF, 20)

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

    dm14 = j1939.MemoryAccess(ca)
    dm14.set_seed_generator(generate_seed)
    dm14.set_notify(global_flag)
    dm14.set_proceed(proceed)
    dm14.set_seed_key_algorithm(key_from_seed)

    ca.send_pgn(
        0,
        (j1939.ParameterGroupNumber.PGN.DM14 >> 8) & 0xFF,
        0xF9 & 0xFF,
        6,
        [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00],
    )

    global flag
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

    dm14 = j1939.MemoryAccess(ca)
    dm14.set_seed_generator(generate_seed)
    dm14.set_notify(global_flag)
    dm14.set_proceed(proceed)
    dm14.set_seed_key_algorithm(key_from_seed)

    ca.send_pgn(
        0,
        (j1939.ParameterGroupNumber.PGN.DM14 >> 8) & 0xFF,
        0xF9 & 0xFF,
        6,
        [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00],
    )

    global flag
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

    dm14 = j1939.MemoryAccess(ca)
    dm14.set_seed_generator(generate_seed)
    dm14.set_proceed(proceed)
    dm14.set_notify(global_flag)
    if expected_messages == request_write_with_seed:
        dm14.set_seed_key_algorithm(key_from_seed)

    ca.send_pgn(
        0,
        (j1939.ParameterGroupNumber.PGN.DM14 >> 8) & 0xFF,
        0xF9 & 0xFF,
        6,
        [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00],
    )

    global flag
    while flag is False:
        pass

    reset_flag()
    test = dm14.respond(True, [], 0xFFFF, 0xFF)
    value = 0x11223344
    assert value == int.from_bytes(test, byteorder="little", signed=False)

    feeder.process_messages()


@pytest.mark.parametrize(
    argnames=["expected_messages"],
    # argvalues=[[request_write_no_seed_8_bytes], [request_write_no_seed_256_bytes]],
    # ids=["Without seed key 8 bytes", "Without seed key 256 bytes"],
    argvalues=[[request_write_no_seed_256_bytes]],
    ids=["Without seed key 256 bytes"],
)
def test_dm14_request_write_large_data(feeder, expected_messages):
    """
    Tests the DM14 response to write query function with large data packet in range (8-255 bytes) and in range (256-1784 bytes)
    :param feeder: can message feeder
    :param expected_messages: list of expected messages
    """
    if expected_messages == request_write_no_seed_8_bytes:
        num_data_bytes = 8
    elif expected_messages == request_write_no_seed_256_bytes:
         num_data_bytes = 256
    else:
        assert False
    feeder.can_messages = expected_messages
    feeder.pdus_from_messages()
    ca = feeder.accept_all_messages(
        device_address_preferred=0xD4, bypass_address_claim=True
    )

    dm14 = j1939.MemoryAccess(ca)
    dm14.set_proceed(proceed)
    dm14.set_notify(global_flag)

    ca.send_pgn(
        0,
        (j1939.ParameterGroupNumber.PGN.DM14 >> 8) & 0xFF,
        0xF9 & 0xFF,
        6,
        [num_data_bytes & 0xFF, ((num_data_bytes & 0x300) >> 3) + 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00],
    )

    global flag
    while flag is False:
        pass

    reset_flag()
    test = dm14.respond(True, [], 0xFFFF, 0xFF)
    values = [0xAB] * num_data_bytes
    assert values == test

    feeder.process_messages()


def test_dm14_request_write_timeout(feeder):
    """
    Tests the DM14 response to write query function timeout waiting for a DM16 response
    :param feeder: can message feeder
    """
    with pytest.raises(queue.Empty) as excinfo:
        feeder.can_messages = request_write_no_seed_timeout
        feeder.pdus_from_messages()
        ca = feeder.accept_all_messages(
            device_address_preferred=0xD4, bypass_address_claim=True
        )

        dm14 = j1939.MemoryAccess(ca)
        dm14.set_seed_generator(generate_seed)
        dm14.set_proceed(proceed)
        dm14.set_notify(global_flag)

        ca.send_pgn(
            0,
            (j1939.ParameterGroupNumber.PGN.DM14 >> 8) & 0xFF,
            0xF9 & 0xFF,
            6,
            [0x01, 0x13, 0x03, 0x00, 0x00, 0x92, 0x07, 0x00],
        )

        global flag
        while flag is False:
            pass

        reset_flag()
        test = dm14.respond(True, [], 0xFFFF, 0xFF)
        assert test == []

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


def test_dm14_read_timeout_error(feeder):
    """
    Tests that the DM14 read query can react to timeout errors correctly
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
        ]

        feeder.pdus_from_messages()

        ca = feeder.accept_all_messages(
            device_address_preferred=0xF9, bypass_address_claim=True
        )

        dm14 = j1939.MemoryAccess(ca)

        dm14.read(0xD4, 1, 0x92000003, 1)

    feeder.process_messages()


def test_dm14_write_timeout(feeder):
    """
    Tests that the DM14 write query can react to timeout errors correctly
    :param feeder: can message feeder
    """
    with pytest.raises(RuntimeError) as excinfo:
        feeder.can_messages = [
            (
                Feeder.MsgType.CANTX,
                0x18D9D4F9,
                [0x01, 0x15, 0x07, 0x00, 0x00, 0x91, 0x07, 0x00],
                0.0,
            ),  # DM14 write address 0x91000007
        ]

        feeder.pdus_from_messages()

        ca = feeder.accept_all_messages(
            device_address_preferred=0xF9, bypass_address_claim=True
        )

        dm14 = j1939.MemoryAccess(ca)

        values = [0x11223344]
        dm14.write(0xD4, 1, 0x91000007, values, object_byte_size=4)
        assert str(excinfo.value) == "No response from server"
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


@pytest.mark.parametrize(
    argnames=["expected_messages"],
    argvalues=[[read_with_seed_error], [read_no_seed_error]],
    ids=["With seed key", "Without seed key"],
)
def test_dm14_read_error_response(feeder, expected_messages):
    """
    Tests that the DM14 read query can react to errors correctly
    :param feeder: can message feeder
    :param expected_messages: list of expected messages
    """
    with pytest.raises(RuntimeError) as excinfo:
        feeder.can_messages = expected_messages
        feeder.pdus_from_messages()
        ca = feeder.accept_all_messages(
            device_address_preferred=0xF9, bypass_address_claim=True
        )
        dm14 = j1939.MemoryAccess(ca)
        dm14.set_seed_key_algorithm(key_from_seed)
        dm14.read(0xD4, 1, 0x92000003, 1)

    assert j1939.ErrorInfo[0x1] in str(excinfo.value)

    feeder.process_messages()


@pytest.mark.parametrize(
    argnames=["expected_messages"],
    argvalues=[[write_with_seed_error], [write_no_seed_error]],
    ids=["With seed key", "Without seed key"],
)
def test_dm14_write_error_response(feeder, expected_messages):
    """
    Tests that the DM14 read query can react to errors correctly
    :param feeder: can message feeder
    :param expected_messages: list of expected messages
    """
    with pytest.raises(RuntimeError) as excinfo:
        feeder.can_messages = expected_messages
        feeder.pdus_from_messages()
        ca = feeder.accept_all_messages(
            device_address_preferred=0xF9, bypass_address_claim=True
        )
        dm14 = j1939.MemoryAccess(ca)
        dm14.set_seed_key_algorithm(key_from_seed)
        values = [0x11223344]
        dm14.write(0xD4, 1, 0x91000007, values, object_byte_size=4)

    assert j1939.ErrorInfo[0x1] in str(excinfo.value)

    feeder.process_messages()


# TODO: moar test
