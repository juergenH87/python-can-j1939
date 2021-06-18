import logging
import time
import can
import j1939

logging.getLogger('j1939').setLevel(logging.DEBUG)
logging.getLogger('can').setLevel(logging.DEBUG)

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
ca = j1939.ControllerApplication(name, 128)


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
    print("PGN {} length {}".format(pgn, len(data)))

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

    # create data with 8 bytes
    data = [j1939.ControllerApplication.FieldValue.NOT_AVAILABLE_8] * 8

    # sending normal broadcast message
    ca.send_pgn(0, 0xFD, 0xED, 6, data)

    # sending normal peer-to-peer message, destintion address is 0x04
    ca.send_pgn(0, 0xE0, 0x04, 6, data)

    # returning true keeps the timer event active
    return True


def ca_timer_callback2(cookie):
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

    # create data with 100 bytes
    data = [j1939.ControllerApplication.FieldValue.NOT_AVAILABLE_8] * 100

    # sending multipacket message with TP-BAM
    ca.send_pgn(0, 0xFE, 0xF6, 6, data)

    # sending multipacket message with TP-CMDT, destination address is 0x05
    ca.send_pgn(0, 0xD0, 0x05, 6, data)

    # returning true keeps the timer event active
    return True

def main():
    print("Initializing")

    # create the ElectronicControlUnit (one ECU can hold multiple ControllerApplications)
    ecu = j1939.ElectronicControlUnit()

    # Connect to the CAN bus
    # Arguments are passed to python-can's can.interface.Bus() constructor
    # (see https://python-can.readthedocs.io/en/stable/bus.html).
    # ecu.connect(bustype='socketcan', channel='can0')
    # ecu.connect(bustype='kvaser', channel=0, bitrate=250000)
    ecu.connect(bustype='pcan', channel='PCAN_USBBUS1', bitrate=250000)
    # ecu.connect(bustype='ixxat', channel=0, bitrate=250000)
    # ecu.connect(bustype='vector', app_name='CANalyzer', channel=0, bitrate=250000)
    # ecu.connect(bustype='nican', channel='CAN0', bitrate=250000)    
    # ecu.connect('testchannel_1', bustype='virtual')

    # add CA to the ECU
    ecu.add_ca(controller_application=ca)
    ca.subscribe(ca_receive)
    # callback every 0.5s
    ca.add_timer(0.500, ca_timer_callback1)
    # callback every 5s
    ca.add_timer(5, ca_timer_callback2)
    # by starting the CA it starts the address claiming procedure on the bus
    ca.start()
                        
    time.sleep(120)

    print("Deinitializing")
    ca.stop()
    ecu.disconnect()

if __name__ == '__main__':
    main()     