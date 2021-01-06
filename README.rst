SAE J1939 for Python
====================

|release| |docs| |build|

.. |release| image:: https://img.shields.io/pypi/v/j1939.svg
   :target: https://pypi.python.org/pypi/j1939/
   :alt: Latest Version on PyPi

.. |docs| image:: https://readthedocs.org/projects/j1939/badge/?version=latest
   :target: https://j1939.readthedocs.io/en/latest/
   :alt: Documentation build Status
                
.. |build| image:: https://travis-ci.com/benkfra/j1939.svg?branch=master
   :target: https://travis-ci.com/benkfra/j1939/branches
   :alt: Travis CI Server for master branch

A new implementation of the CAN SAE J1939 standard for Python.

WARNING: Currently this project is in alpha-state! Some of the features are not completely working! 

If you experience a problem or think the stack would not behave properly, do 
not hesitate to open a ticket or write an email.
Pullrequests are of course even more welcome!

The project uses the python-can_ package to support multiple hardware drivers. 
At the time of writing the supported interfaces are 

* CAN over Serial
* CAN over Serial / SLCAN
* IXXAT Virtual CAN Interface
* Kvaser’s CANLIB
* NEOVI Interface
* NI-CAN
* PCAN Basic API
* Socketcan
* USB2CAN Interface
* Vector
* Virtual
* isCAN

Overview
--------

An SAE J1939 CAN Network consists of multiple Electronic Control Units (ECUs). 
Each ECU can have one or more Controller Applications (CAs). Each CA has its 
own (unique) Address on the bus. This address is either acquired within the 
address claiming procedure or set to a fixed value. In the latter case, the CA
has to announce its address to the bus to check whether it is free.

The CAN messages in a SAE J1939 network are called Protocol Data Units (PDUs).
This definition is not completely correct, but close enough to think of PDUs 
as the CAN messages.


Features
--------

* one ElectronicControlUnit (ECU) can hold multiple ControllerApplications (CA)
* ECU (CA) Naming according SAE J1939/81
* (under construction) full featured address claiming procedure according SAE J1939/81
* full support of transport protocol according SAE J1939/21 for sending and receiveing

  - Message Packaging and Reassembly (up to 1785 bytes)

    + Transfer Protocol Transfer Data (TP.TD)
    + Transfer Protocol Communication Management (TP.CM)

  - Multi-Packet Broadcasts

    + Broadcast Announce Message (TP.BAM)

* (under construction) Requests (global and specific)
* (under construction) correct timeout and deadline handling
* (under construction) almost complete testcoverage


Installation
------------

As soon the package is available in your distro, it's as easy as::

    $ pip install j1939

In the meanwhile you can either download the wheel-package and issue the command::

    $ pip install j1939-0.1.0.dev1-py2.py3-none-any.whl

or do the trick with::

    $ git clone https://github.com/benkfra/j1939.git
    $ cd j1939
    $ pip install .

If you want to be able to change the code while using it, clone it then install it in `develop mode`_::

    $ git clone https://github.com/benkfra/j1939.git
    $ cd j1939
    $ pip install -e .


Quick start
-----------

To simply receive all passing (public) messages on the bus you can subscribe to the ECU object.

.. code-block:: python

    import logging
    import time
    import can
    import j1939

    logging.getLogger('j1939').setLevel(logging.DEBUG)
    logging.getLogger('can').setLevel(logging.DEBUG)

    def on_message(pgn, data):
        """Receive incoming messages from the bus

        :param int pgn:
            Parameter Group Number of the message
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

A more sophisticated example in which the CA class was overloaded to include its own functionality:

.. code-block:: python

    import logging
    import time
    import can
    import j1939

    logging.getLogger('j1939').setLevel(logging.DEBUG)
    logging.getLogger('can').setLevel(logging.DEBUG)

    class OwnCaToProduceCyclicMessages(j1939.ControllerApplication):
        """CA to produce messages

        This CA produces simulated sensor values and cyclically sends them to
        the bus with the PGN 0xFEF6 (Intake Exhaust Conditions 1).
        """

        def __init__(self, name, device_address_preferred=None):
            # old fashion calling convention for compatibility with Python2
            j1939.ControllerApplication.__init__(self, name, device_address_preferred)

        def start(self):
            """Starts the CA
            (OVERLOADED function)
            """
            # add our timer event
            self._ecu.add_timer(0.500, self.timer_callback)
            # call the super class function
            return j1939.ControllerApplication.start(self)

        def stop(self):
            """Stops the CA
            (OVERLOADED function)
            """
            self._ecu.remove_timer(self.timer_callback)

        def on_message(self, pgn, data):
            """Feed incoming message to this CA.
            (OVERLOADED function)
            :param int pgn:
                Parameter Group Number of the message
            :param bytearray data:
                Data of the PDU
            """
            print("PGN {} length {}".format(pgn, len(data)))

        def timer_callback(self, cookie):
            """Callback for sending the IEC1 message

            This callback is registered at the ECU timer event mechanism to be 
            executed every 500ms.

            :param cookie:
                A cookie registered at 'add_timer'. May be None.
            """
            # wait until we have our device_address
            if self.state != j1939.ControllerApplication.State.NORMAL:
                # returning true keeps the timer event active
                return True

            pgn = j1939.ParameterGroupNumber(0, 0xFE, 0xF6)
            data = [
                j1939.ControllerApplication.FieldValue.NOT_AVAILABLE_8, # Particulate Trap Inlet Pressure (SPN 81)
                j1939.ControllerApplication.FieldValue.NOT_AVAILABLE_8, # Boost Pressure (SPN 102)
                j1939.ControllerApplication.FieldValue.NOT_AVAILABLE_8, # Intake Manifold 1 Temperature (SPN 105)
                j1939.ControllerApplication.FieldValue.NOT_AVAILABLE_8, # Air Inlet Pressure (SPN 106)
                j1939.ControllerApplication.FieldValue.NOT_AVAILABLE_8, # Air Filter 1 Differential Pressure (SPN 107)
                j1939.ControllerApplication.FieldValue.NOT_AVAILABLE_16_ARR[0], # Exhaust Gas Temperature (SPN 173)
                j1939.ControllerApplication.FieldValue.NOT_AVAILABLE_16_ARR[1],
                j1939.ControllerApplication.FieldValue.NOT_AVAILABLE_8, # Coolant Filter Differential Pressure (SPN 112)
                ]

            # SPN 105, Range -40..+210
            # (Offset -40)
            receiverTemperature = 30
            data[2] = receiverTemperature + 40

            self.send_message(6, pgn.value, data)

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

        # create derived CA with given NAME and ADDRESS
        ca = OwnCaToProduceCyclicMessages(name, 128)
        # add CA to the ECU
        ecu.add_ca(controller_application=ca)
        # by starting the CA it starts the address claiming procedure on the bus
        ca.start()

        time.sleep(120)

        print("Deinitializing")
        ca.stop()
        ecu.disconnect()

    if __name__ == '__main__':
        main()        

Credits
-------

This implementation was initially inspired by the `CANopen project of Christian Sandberg`_.
Thanks for your great work!

Most of the informations about SAE J1939 are taken from the papers and the book of 
`Copperhill technologies`_ and from my many years of experience in J1939 of course :-)



.. _python-can: https://python-can.readthedocs.org/en/stable/
.. _develop mode: https://packaging.python.org/distributing/#working-in-development-mode
.. _Copperhill technologies: http://copperhilltech.com/a-brief-introduction-to-the-sae-j1939-protocol/
.. _CANopen project of Christian Sandberg: http://canopen.readthedocs.io/en/stable/
