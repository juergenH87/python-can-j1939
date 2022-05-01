import logging
import time
import can
import j1939
from hexdump import hexdump

logging.getLogger('j1939').setLevel(logging.DEBUG)
logging.getLogger('can').setLevel(logging.DEBUG)

MY_ADDR = 1
# compose the name descriptor for the new ca
name = j1939.Name(
    arbitrary_address_capable=0,
    industry_group=j1939.Name.IndustryGroup.Industrial,
    vehicle_system_instance=1,
    vehicle_system=1,
    function=1,
    function_instance=1,
    ecu_instance=1,
    manufacturer_code=666,
    identity_number=1234567
    )

# create the ControllerApplications
ca = j1939.ControllerApplication(name, MY_ADDR)

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
    print(f"PGN {pgn} length {len(data)} source {hex(sa)} time {timestamp} my_addr {hex(MY_ADDR)}")
    # print(hexdump(data))

def main():
    print("Initializing")

    # create the ElectronicControlUnit (one ECU can hold multiple ControllerApplications)
    ecu = j1939.ElectronicControlUnit()

    # Connect to the CAN bus
    # Arguments are passed to python-can's can.interface.Bus() constructor
    # (see https://python-can.readthedocs.io/en/stable/bus.html).
    ecu.connect(bustype='socketcan', channel='can0')
    # ecu.connect(bustype='kvaser', channel=0, bitrate=250000)
    # ecu.connect(bustype='pcan', channel='PCAN_USBBUS1', bitrate=250000)
    # ecu.connect(bustype='ixxat', channel=0, bitrate=250000)
    # ecu.connect(bustype='vector', app_name='CANalyzer', channel=0, bitrate=250000)
    # ecu.connect(bustype='nican', channel='CAN0', bitrate=250000)

    # add CA to the ECU
    ecu.add_ca(controller_application=ca)
    ca.subscribe(on_message)
    ca.start()

    print("Initialized")

    time.sleep(300)

    print("Deinitializing")
    ca.stop()
    ecu.disconnect()

if __name__ == '__main__':
    main()
