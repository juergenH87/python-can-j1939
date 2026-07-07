import logging
import time

import j1939

logging.getLogger('j1939').setLevel(logging.DEBUG)
logging.getLogger('can').setLevel(logging.DEBUG)

def on_message(priority, pgn, sa, timestamp, data):
    """Receive incoming messages from the bus

    :param int priority:
        Priority of the message
    :param int pgn:
        Parameter Group Number of the message
    :param int sa:
        Source Address of the message
    :param int timestamp:
        Timestamp of the message
    :param bytearray data:
        Data of the PDU
    """
    print(f"PGN {hex(pgn)} length {len(data)}")

def main():
    print("Initializing")

    # create the ElectronicControlUnit (one ECU can hold multiple ControllerApplications)
    ecu = j1939.ElectronicControlUnit()

    # Connect to the CAN bus
    # Arguments are passed to python-can's can.interface.Bus() constructor
    # (see https://python-can.readthedocs.io/en/stable/bus.html).
    # ecu.connect(interface='socketcan', channel='can0')
    # ecu.connect(interface='kvaser', channel=0, bitrate=250000)
    ecu.connect(interface='pcan', channel='PCAN_USBBUS1', bitrate=500000)
    # ecu.connect(interface='ixxat', channel=0, bitrate=250000)
    # ecu.connect(interface='vector', app_name='CANalyzer', channel=0, bitrate=250000)
    # ecu.connect(interface='nican', channel='CAN0', bitrate=250000)

    # subscribe to all global and peer-to-peer messages with destination 0xFA
    ecu.subscribe(on_message, 0xFA)

    time.sleep(120)

    print("Deinitializing")
    ecu.disconnect()

if __name__ == '__main__':
    main()
