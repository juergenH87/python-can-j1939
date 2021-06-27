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
    print("PGN {} length {}".format(pgn, len(data)), timestamp)


def ca_timer_callback1(ca):
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

    # create data with 20 bytes
    data = [j1939.ControllerApplication.FieldValue.NOT_AVAILABLE_8] * 20

    # sending broadcast message
    # the following two PGNs are packed into one multi-pg, due to time-limit of 10ms and same destination address (global)
    ca.send_pgn(0, 0xFD, 0xED, 6, data, time_limit=0.01)
    ca.send_pgn(0, 0xFE, 0x32, 6, data, time_limit=0.01)

    # sending normal peer-to-peer message, destintion address is 0x04
    # the following PGNs are transferred separately, because time limit == 0
    ca.send_pgn(0, 0xE0, 0x04, 6, data)
    ca.send_pgn(0, 0xD0, 0x04, 6, data)

    # returning true keeps the timer event active
    return True


def main():
    print("Initializing")

    # create the ElectronicControlUnit (one ECU can hold multiple ControllerApplications) with j1939-22 data link layer
    ecu = j1939.ElectronicControlUnit(data_link_layer='j1939-22', max_cmdt_packets=200)

    # can fd Baud: 500k/2M
    ecu.connect(bustype='pcan', channel='PCAN_USBBUS1', fd=True,
                        f_clock_mhz=80, nom_brp=10, nom_tseg1=12, nom_tseg2=3, nom_sjw=1, data_brp=4, data_tseg1=7, data_tseg2=2, data_sjw=1)

    # subscribe to all (global) messages on the bus
    ecu.subscribe(on_message)

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
    ca = j1939.ControllerApplication(name, 0x1)
    ecu.add_ca(controller_application=ca)
    # callback every 0.5s
    ca.add_timer(0.500, ca_timer_callback1, ca)
    ca.start()

    time.sleep(120)

    print("Deinitializing")
    ca.stop()
    ecu.disconnect()

if __name__ == '__main__':
    main()