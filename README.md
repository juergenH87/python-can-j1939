# SAE J1939 for Python

[![Latest Version on PyPi](https://img.shields.io/pypi/v/python-can-j1939)](https://pypi.org/project/python-can-j1939/)
[![Documentation build Status](https://readthedocs.org/projects/python-can-j1939/badge/?version=latest)](https://python-can-j1939.readthedocs.io/en/latest/)

An implementation of the CAN SAE J1939 standard for Python. This is the
first J1939-22 (J1939-FD) implementation!

If you experience a problem or think the stack would not behave
properly, do not hesitate to open a ticket or write an email.
Pull Requests (PR) are of course even more welcome!

The project uses the
[python-can](https://python-can.readthedocs.org/en/stable/) package to
support multiple hardware drivers. At the time of writing the supported
interfaces are

- CAN over Serial
- CAN over Serial / SLCAN
- CANalyst-II
- IXXAT Virtual CAN Interface
- Kvasers CANLIB
- NEOVI Interface
- NI-CAN
- PCAN Basic API
- Socketcan
- SYSTEC interface
- USB2CAN Interface
- Vector
- Virtual
- isCAN

## Overview

An SAE J1939 CAN Network consists of multiple Electronic Control Units
(ECUs). Each ECU can have one or more Controller Applications (CAs).
Each CA has its own (unique) Address on the bus. This address is either
acquired within the address claiming procedure or set to a fixed value.
In the latter case, the CA has to announce its address to the bus to
check whether it is free.

The CAN messages in a SAE J1939 network are called Protocol Data Units
(PDUs). This definition is not completely correct, but close enough to
think of PDUs as the CAN messages.

## Features

- one ElectronicControlUnit (ECU) can hold multiple
    ControllerApplications (CA)
- ECU (CA) Naming according SAE J1939/81
- full featured address claiming procedure according SAE J1939/81
- full support of transport protocol (up to 1785 bytes) according SAE
    J1939/21 for sending and receiving
  - Connection Mode Data Transfers (CMDT)
  - Broadcast Announce Message (BAM)
- support of Multi-PG according SAE J1939/22
  - currently FEFF (Flexible Data Rate Extended Frame Format)
        supported only
- full support of fd-transport protocol according SAE J1939/22
    (J1939-FD) for sending and receiving
  - RTS/CTS (Destination Specific) Transfer with up to 8 concurrent
        sessions and up to 16777215 bytes of data per session
  - Broadcast Announce Message (BAM) with up to 4 concurrent
        sessions and up to 15300 bytes of data per session
- Requests (global and specific)
- correct timeout and deadline handling
- (under construction) almost complete testcoverage
- diagnostic messages (see
    <https://github.com/RaulSMS/python-can-j1939/tree/master/examples/diagnostic_message.py>)
  - support of DM1 Tool and ECU functionaliy (all four SAE J1939-73
        SPN conversion methods: 1, 2, 3, 4)
  - support of DM11 Tool functionaliy
  - support of DM22 Tool functionaliy

## Installation

Requires **Python 3.10 or later** and python-can_ >= 4.2.0.

Install python-can-j1939 with pip:

    pip install python-can-j1939

or do the trick with:

    git clone https://github.com/RaulSMS/python-can-j1939.git
    cd python-can-j1939
    pip install .

## Upgrade

Upgrade an already installed python-can-j1939 package:

    pip install --upgrade python-can-j1939

## Quick start

To simply receive all passing (public) messages on the bus you can
subscribe to the ECU object.

``` python
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
    print("PGN {} length {}".format(pgn, len(data)))

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

    time.sleep(120)

    print("Deinitializing")
    ecu.disconnect()

if __name__ == '__main__':
    main()
```

A more sophisticated example in which the CA class was overloaded to
include its own functionality:

``` python
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
```

## Credits

This package is a fork of
[can-j1939](https://github.com/juergenH87/python-can-j1939) by Juergen
Heilgemeir, who greatly extended the original work and added J1939-22
(J1939-FD) support.

The original implementation was taken from
<https://github.com/benkfra/j1939> by Frank Benkert.

Thanks to all contributors for their great work!
