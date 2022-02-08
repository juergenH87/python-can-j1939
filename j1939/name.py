
class Name:
    """The Name of one Controller Application.

    The Name consists of 64 bit:

        1-bit Arbitrary Address Capable
        Indicate the capability to solve address conflicts.
        Set to 1 if the device is Arbitrary Address Capable, set to 0 if
        it's Single Address Capable.

        3-bit Industry Group
        One of the predefined J1939 industry groups.

        4-bit Vehicle System Instance
        Instance number of a vehicle system to distinguish two or more
        device with the same Vehicle System number in the same J1939
        network.
        The first instance is assigned to the instance number 0.

        7-bit Vehicle System
        A subcomponent of a vehicle, that includes one or more J1939
        segments and may be connected or disconnected from the vehicle.
        A Vehicle System may be made of one or more functions. The Vehicle
        System depends on the Industry Group definition.

        1-bit Reserved
        This field is reserved for future use by SAE.

        8-bit Function
        One of the predefined J1939 functions. The same function value
        (upper 128 only) may mean different things for different Industry
        Groups or Vehicle Systems.

        5-bit Function Instance
        Instance number of a function to distinguish two or more devices
        with the same function number in the same J1939 network.
        The first instance is assigned to the instance number 0.

        3-bit ECU Instance
        Identify the ECU instance if multiple ECUs are involved in
        performing a single function. Normally set to 0.

        11-bit Manufacturer Code
        One of the predefined J1939 manufacturer codes.

        21-bit Identity Number
        A unique number which identifies the particular device in a
        manufacturer specific way.
    """

    class IndustryGroup:
        Global = 0
        OnHighway = 1
        AgriculturalAndForestry = 2
        Construction = 3
        Marine = 4
        Industrial = 5

    def __init__(self, **kwargs):
        """
        :param value:
            64-bit value the address should be extracted from

        :param bytes:
            Array of 8 bytes containing the name object as binary representation.

        :param arbitrary_address_capable:
            1-bit Arbitrary Address Capable
            Indicate the capability to solve address conflicts.
            Set to 1 if the device is Arbitrary Address Capable, set to 0 if
            it's Single Address Capable.
        :param industry_group:
            3-bit Industry Group
            One of the predefined J1939 industry groups.
        :param vehicle_system_instance:
            4-bit Vehicle System Instance
            Instance number of a vehicle system to distinguish two or more
            device with the same Vehicle System number in the same J1939
            network.
            The first instance is assigned to the instance number 0.
        :param vehicle_system:
            7-bit Vehicle System
            A subcomponent of a vehicle, that includes one or more J1939
            segments and may be connected or disconnected from the vehicle.
            A Vehicle System may be made of one or more functions. The Vehicle
            System depends on the Industry Group definition.
        :param function:
            8-bit Function
            One of the predefined J1939 functions. The same function value
            (upper 128 only) may mean different things for different Industry
            Groups or Vehicle Systems.
        :param function_instance:
            5-bit Function Instance
            Instance number of a function to distinguish two or more devices
            with the same function number in the same J1939 network.
            The first instance is assigned to the instance number 0.
        :param ecu_instance:
            3-bit ECU Instance
            Identify the ECU instance if multiple ECUs are involved in
            performing a single function. Normally set to 0.
        :param manufacturer_code:
            11-bit Manufacturer Code
            One of the predefined J1939 manufacturer codes.
        :param identity_number:
            21-bit Identity Number
            A unique number which identifies the particular device in a
            manufacturer specific way.
        """
        if 'value' in kwargs:
            self.value = kwargs['value']
        elif 'bytes' in kwargs:
            self.bytes = kwargs['bytes']
        else:
            self.arbitrary_address_capable = kwargs.get('arbitrary_address_capable', False)
            if (self.arbitrary_address_capable < 0) or (self.arbitrary_address_capable > 1):
                raise ValueError("Length of arbitrary address capable incorrect")
            self.industry_group = kwargs.get('industry_group', Name.IndustryGroup.Global)
            if (self.industry_group < 0) or (self.industry_group > ((2 ** 3) - 1)):
                raise ValueError("Length of industry group incorrect")
            self.vehicle_system_instance = kwargs.get('vehicle_system_instance', 0)
            if (self.vehicle_system_instance < 0) or (self.vehicle_system_instance > ((2 ** 4) - 1)):
                raise ValueError("Length of vehicle system instance incorrect")
            self.vehicle_system = kwargs.get('vehicle_system', 0)
            if (self.vehicle_system < 0) or (self.vehicle_system > ((2 ** 7) - 1)):
                raise ValueError("Length of vehicle system incorrect")
            self.function = kwargs.get('function', 0)
            if (self.function < 0) or (self.function > ((2 ** 8) - 1)):
                raise ValueError("Length of function incorrect")
            self.function_instance = kwargs.get('function_instance', 0)
            if (self.function_instance < 0) or (self.function_instance > ((2 ** 5) - 1)):
                raise ValueError("Length of function instance incorrect")
            self.ecu_instance = kwargs.get('ecu_instance', 0)
            if (self.ecu_instance < 0) or (self.ecu_instance > ((2 ** 3) - 1)):
                raise ValueError("Length of ecu instance incorrect")
            self.manufacturer_code = kwargs.get('manufacturer_code', 0)
            if (self.manufacturer_code < 0) or (self.manufacturer_code > ((2 ** 11) - 1)):
                raise ValueError("Length of manufacturer code incorrect")
            self.identity_number = kwargs.get('identity_number', 0)
            if (self.identity_number < 0) or (self.identity_number > ((2 ** 21) - 1)):
                raise ValueError("Length of identity number incorrect")

        self.reserved_bit = 0

    @property
    def arbitrary_address_capable(self):
        return self.__arbitrary_address_capable

    @arbitrary_address_capable.setter
    def arbitrary_address_capable(self, value):
        self.__arbitrary_address_capable = value

    @property
    def industry_group(self):
        return self.__industry_group

    @industry_group.setter
    def industry_group(self, value):
        self.__industry_group = value

    @property
    def vehicle_system_instance(self):
        return self.__vehicle_system_instance

    @vehicle_system_instance.setter
    def vehicle_system_instance(self, value):
        self.__vehicle_system_instance = value

    @property
    def vehicle_system(self):
        return self.__vehicle_system

    @vehicle_system.setter
    def vehicle_system(self, value):
        self.__vehicle_system = value

    @property
    def reserved_bit(self):
        return self.__reserved_bit

    @reserved_bit.setter
    def reserved_bit(self, value):
        self.__reserved_bit = value

    @property
    def function(self):
        return self.__function

    @function.setter
    def function(self, value):
        self.__function = value

    @property
    def function_instance(self):
        return self.__function_instance

    @function_instance.setter
    def function_instance(self, value):
        self.__function_instance = value

    @property
    def ecu_instance(self):
        return self.__ecu_instance

    @ecu_instance.setter
    def ecu_instance(self, value):
        self.__ecu_instance = value

    @property
    def manufacturer_code(self):
        return self.__manufacturer_code

    @manufacturer_code.setter
    def manufacturer_code(self, value):
        self.__manufacturer_code = value

    @property
    def identity_number(self):
        return self.__identity_number

    @identity_number.setter
    def identity_number(self, value):
        self.__identity_number = value

    @property
    def value(self):
        retval = self.identity_number
        retval += (self.manufacturer_code << 21)
        retval += (self.ecu_instance << 32)
        retval += (self.function_instance << 35)
        retval += (self.function << 40)
        retval += (self.reserved_bit << 48)
        retval += (self.vehicle_system << 49)
        retval += (self.vehicle_system_instance << 56)
        retval += (self.industry_group << 60)
        retval += (self.arbitrary_address_capable << 63)
        return retval

    @value.setter
    def value(self, value):
        self.identity_number = value & ((2 ** 21) - 1)
        self.manufacturer_code = (value >> 21) & ((2 ** 11) - 1)
        self.ecu_instance = (value >> 32) & ((2 ** 3) - 1)
        self.function_instance = (value >> 35) & ((2 ** 5) - 1)
        self.function = (value >> 40) & ((2 ** 8) - 1)
        self.reserved_bit = (value >> 48) & 1
        self.vehicle_system = (value >> 49) & ((2 ** 7) - 1)
        self.vehicle_system_instance = (value >> 56) & ((2 ** 4) - 1)
        self.industry_group = (value >> 60) & ((2 ** 3) - 1)
        self.arbitrary_address_capable = (value >> 63) & 1

    @property
    def bytes(self):
        """Get the Name object as 8 Byte Data"""
        return [
            ((self.value >>  0) & 0xFF),
            ((self.value >>  8) & 0xFF),
            ((self.value >> 16) & 0xFF),
            ((self.value >> 24) & 0xFF),
            ((self.value >> 32) & 0xFF),
            ((self.value >> 40) & 0xFF),
            ((self.value >> 48) & 0xFF),
            ((self.value >> 56) & 0xFF)
        ]

    @bytes.setter
    def bytes(self, value):
        self.value = int.from_bytes(value, byteorder='little', signed=False)
