import logging
import time
import can
import j1939
import os
from hexdump import hexdump

logging.getLogger('j1939').setLevel(logging.DEBUG)
logging.getLogger('can').setLevel(logging.DEBUG)

MY_ADDR = 0x03
MAX_PACKET_SIZE = 1785

# compose the name descriptor for the new ca
name = j1939.Name(
    arbitrary_address_capable=1,
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

def ca_receive(priority, pgn, source, timestamp, data):
    """Feed incoming message to this CA.
    (OVERLOADED function)
    :param int priority:
        Priority of the message
    :param int pgn:
        Parameter Group Number of the message
    :param intsa:
        Source Address of the message
    :param int timestamp:
        Timestamp of the message
    :param bytearray data:
        Data of the PDU
    """
    print(f"PGN {pgn} length {len(data)} source {source} time {timestamp} my_addr {hex(MY_ADDR)}")
    print(hexdump(data))

def ca_send_broadcast_pgn(size=100):
    # wait until we have our device_address
    while ca.state != j1939.ControllerApplication.State.NORMAL:
        time.sleep(1)
        continue

    print(f"sending {size} bytes")
    # create custom length data
    # data = [j1939.ControllerApplication.FieldValue.NOT_AVAILABLE_8] * size
    data = [0x01] * size

    # sending normal broadcast message
    ca.send_pgn(0, 0xFD, 0xED, 6, data)
    print(f"sent {size} bytes to broadcast")

    return True

def ca_send_direct_pgn(dest, size=100):
    # wait until we have our device_address
    while ca.state != j1939.ControllerApplication.State.NORMAL:
        time.sleep(1)
        continue

    # create custom length data
    data = [j1939.ControllerApplication.FieldValue.NOT_AVAILABLE_8] * size

    # sending normal peer-to-peer message
    ca.send_pgn(0, 0xE0, dest, 6, data)
    print(f"sent {size} bytes to {hex(dest)}")
    return True

def ca_timer_callback1(cookie):
    """Callback for sending messages

    This callback is registered at the ECU timer event mechanism to be
    executed every 500ms.

    :param cookie:
        A cookie registered at 'add_timer'. May be None.
    """
    # wait until we have our device_address
    if ca.state != j1939.ControllerApplication.State.NORMAL:
        # returning true keeps the timer event active
        return True

    ca_send_direct_pgn(0x1, 100)
    ca_send_direct_pgn(0x2, 100)

    # returning true keeps the timer event active
    return True

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
    ca.subscribe(ca_receive)

    # setup periodic message callbacks
    ca.add_timer(2, ca_timer_callback1)

    # by starting the CA it starts the address claiming procedure on the bus
    ca.start()
    print("waiting for addr ...")

    time.sleep(120)

    print("Deinitializing")
    ca.stop()
    ecu.disconnect()

if __name__ == '__main__':
    main()