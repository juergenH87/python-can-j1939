"""ISO 11783-3 ETP receiver example.

Run alongside j1939_send.py. Incoming ETP messages are reassembled by the
stack and delivered to the subscribed callback exactly like a short PGN.
"""

import logging
import time

import j1939

logging.getLogger('j1939').setLevel(logging.DEBUG)
logging.getLogger('can').setLevel(logging.DEBUG)

MY_ADDR = 0x01

name = j1939.Name(
    arbitrary_address_capable=0,
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


def on_message(priority, pgn, sa, timestamp, data):
    print(f"PGN {pgn} length {len(data)} source {hex(sa)} time {timestamp}")


def main():
    print("Initializing")

    # max_cmdt_packets bumps the per-CTS burst size; tune for your link.
    ecu = j1939.ElectronicControlUnit(max_cmdt_packets=255)
    ecu.connect(bustype='socketcan', channel='can0')
    # ecu.connect(bustype='pcan', channel='PCAN_USBBUS1', bitrate=250000)
    # ecu.connect(bustype='vector', app_name='CANalyzer', channel=0, bitrate=250000)

    ecu.add_ca(controller_application=ca)
    ca.subscribe(on_message)
    ca.start()

    print("Initialized")
    time.sleep(120)

    print("Deinitializing")
    ca.stop()
    ecu.disconnect()


if __name__ == '__main__':
    main()
