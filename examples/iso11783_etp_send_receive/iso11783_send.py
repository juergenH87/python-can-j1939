"""ISO 11783-3 ETP sender example.

Sends a destination-specific message larger than the J1939-21 TP limit
(1785 bytes). The stack automatically routes it through ETP: ETP.CM_RTS,
ETP.CM_CTS, ETP.CM_DPO, a burst of ETP.DT packets, and ETP.CM_EOMA.

Run together with iso11783_receive.py on the same CAN bus. Update MY_ADDR /
DEST_ADDR if you change the addresses.
"""

import logging
import time

import j1939

logging.getLogger('j1939').setLevel(logging.DEBUG)
logging.getLogger('can').setLevel(logging.DEBUG)

MY_ADDR = 0x03
DEST_ADDR = 0x01

# Use a peer-to-peer (PDU1) PGN. PF=223 (0xDF), PS becomes the destination.
ETP_PGN_PF = 0xDF

name = j1939.Name(
    arbitrary_address_capable=1,
    industry_group=j1939.Name.IndustryGroup.Industrial,
    vehicle_system_instance=1,
    vehicle_system=1,
    function=1,
    function_instance=1,
    ecu_instance=1,
    manufacturer_code=666,
    identity_number=1234567,
)

ca = j1939.ControllerApplication(name, MY_ADDR)


def ca_receive(priority, pgn, source, timestamp, data):
    print(f"PGN {pgn} length {len(data)} source {hex(source)} time {timestamp}")


def ca_send_etp(size=5000):
    while ca.state != j1939.ControllerApplication.State.NORMAL:
        time.sleep(1)
    payload = [i & 0xFF for i in range(size)]
    print(f"sending {size} bytes via ETP to {hex(DEST_ADDR)}")
    # Anything > 1785 bytes to a non-global destination triggers ETP automatically.
    ca.send_pgn(0, ETP_PGN_PF, DEST_ADDR, 6, payload)
    print("send_pgn returned (ETP runs asynchronously)")


def ca_timer_callback(cookie):
    if ca.state != j1939.ControllerApplication.State.NORMAL:
        return True
    ca_send_etp(size=5000)
    # Stop after the first send so we don't flood the bus.
    return False


def main():
    print("Initializing")

    # max_cmdt_packets bumps the per-CTS burst size; tune for your link.
    ecu = j1939.ElectronicControlUnit(max_cmdt_packets=255)
    ecu.connect(bustype='socketcan', channel='can0')
    # ecu.connect(bustype='pcan', channel='PCAN_USBBUS1', bitrate=250000)
    # ecu.connect(bustype='vector', app_name='CANalyzer', channel=0, bitrate=250000)

    ecu.add_ca(controller_application=ca)
    ca.subscribe(ca_receive)
    ca.add_timer(2, ca_timer_callback)
    ca.start()
    print("waiting for addr ...")

    time.sleep(60)

    print("Deinitializing")
    ca.stop()
    ecu.disconnect()


if __name__ == '__main__':
    main()
