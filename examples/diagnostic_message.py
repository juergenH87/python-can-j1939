import logging
import time
import can
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

    # get DM1 message
    Dm1 = j1939.DiagnosticMessage1(pgn, data)
    if Dm1 != None:
        # DM1 lamp status
        print("\nDM1 received from source", sa, ", number DTC", len(Dm1.dtc_list))
        print("lamp status", Dm1.lamp_status)
        spn_fmi = []
        for dtc in Dm1.dtc_list:
            # print all DTCs of DM1
            # a DTC consits of s SPN, FMI and an occurrence counter, only 0 is supported as SPN conversion mode
            spn_fmi.append({j1939.DTC(dtc).spn, j1939.DTC(dtc).fmi})
        print("spn/fmi list", spn_fmi)


def main():
    print("Initializing")

    # create the ElectronicControlUnit (one ECU can hold multiple ControllerApplications)
    ecu = j1939.ElectronicControlUnit()

    # Connect to the CAN bus
    # Arguments are passed to python-can's can.interface.Bus() constructor
    # (see https://python-can.readthedocs.io/en/stable/bus.html).
    # ecu.connect(bustype='socketcan', channel='can0')
    # ecu.connect(bustype='kvaser', channel=0, bitrate=250000)
    ecu.connect(bustype='pcan', channel='PCAN_USBBUS1', bitrate=500000)
    # ecu.connect(bustype='ixxat', channel=0, bitrate=250000)
    # ecu.connect(bustype='vector', app_name='CANalyzer', channel=0, bitrate=250000)
    # ecu.connect(bustype='nican', channel='CAN0', bitrate=250000)    

    # subscribe to all (global) messages on the bus
    ecu.subscribe(on_message)

    time.sleep(120)

    print("Deinitializing")
    ecu.disconnect()

if __name__ == '__main__':
    main()