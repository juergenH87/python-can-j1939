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
    pass


def dm1_receive(sa, lamp_status, dtc_dic_list, timestamp):
    """Receive incoming Dm1 messages from the bus

    :param int sa:
        Source Address of the message
    :param dic lamp_status:
        lamp status dictionary
        keys: 'pl', 'awl', 'rsl', 'mil'
        value: j1939.DtcLamp.OFF / .ON / .SLOW_FLASH / .ON_FAST_FLASH
    :param list of dic dtc_dic_list:
        DTC List
        keys: 'spn', 'fmi', 'oc'
    :param int timestamp:
        Timestamp of the message
    :param bytearray data:
        Data of the PDU
    """
    print('DM1 received from address:', sa, 'lamp status:', lamp_status, 'DTCs:', dtc_dic_list)


def dm1_before_send():
    """This function is called before a Dm1 message is sent to collect the data
 
    :return:
        lamp status 
    :rtype: dic: 'pl', 'awl', 'rsl', 'mil'
    
    :return:
        list of dictionaries of all DTCs included in DM1

    :rtype: list of dic: 'spn', 'fmi', 'oc'
    """
    lamp_status = {}
    # get lamp status (optional, if status not enter, lamp is switched off)
    lamp_status['pl']  = j1939.DtcLamp.ON_FAST_FLASH
    lamp_status['awl'] = j1939.DtcLamp.ON_SLOW_FLASH
    lamp_status['rsl'] = j1939.DtcLamp.NA
    lamp_status['mil'] = j1939.DtcLamp.OFF

    # add all active DTCs
    # if no DTC is active return empty list
    dtc_list = []
    dtc_list.append({'spn': 123, 'fmi': 31})           # occurrence counter is set to 0
    dtc_list.append({'spn': 456, 'fmi': 1, 'oc': 132}) # with optional occurrence counter

    return lamp_status, dtc_list


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

    # subscribe to all (global) messages on the bus
    ecu.subscribe(on_message)

    # name descriptor for the ca
    CA_NAME = j1939.Name(
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
    ca = j1939.ControllerApplication(CA_NAME, 0xF1)
    # add CA to the ECU
    ecu.add_ca(controller_application=ca)
    # by starting the CA it starts the address claiming procedure on the bus
    ca.start()


    # create the instance of the Dm1 to be able to receive active DTCs
    Dm1_rec = j1939.Dm1(ca)
    # subscribe to DM1-messages on the bus
    Dm1_rec.subscribe(dm1_receive)

    # create the instance of the Dm1 to be able to send active DTCs
    Dm1_snd = j1939.Dm1(ca)
    # start sending Dm1-message from source-id 10
    Dm1_snd.start_send(callback=dm1_before_send)


    time.sleep(120)

    print("Deinitializing")
    ecu.disconnect()

if __name__ == '__main__':
    main()