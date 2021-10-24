
class MessageId:
    """The CAN MessageId of an PDU.

    The MessageId consists of three parts:
      * Priority
      * Parameter Group Number
      * Source Address
    """

    def __init__(self, **kwargs): #priority=0, parameter_group_number=0, source_address=0):
        """
        :param priority:
            3-bit Priority
        :param parameter_group_number:
            18-bit Parameter Group Number
        :param source_address:
            8-bit Source Address
            There is a total of 253 addresses available and every address must
            be unique within the network.

        :param can_id:
            A 29-bit CAN-Id the MessageId should be parsed from.
        """

        if 'can_id' in kwargs:
            # let the property can_id parse the given value
            self.can_id = kwargs.get('can_id')
        else:
            self.priority = kwargs.get('priority', 0) & 7
            self.parameter_group_number = kwargs.get('parameter_group_number', 0) & 0x3FFFF
            self.source_address = kwargs.get('source_address', 0) & 0xFF

    @property
    def can_id(self):
        """Transforms the MessageId object to a 29 bit CAN-Id"""
        return (self.priority << 26) | (self.parameter_group_number << 8) | (self.source_address)

    @can_id.setter
    def can_id(self, can_id):
        """Fill the MessageId with the information given in the 29 bit CAN-Id"""
        self.source_address = can_id & 0xFF
        self.parameter_group_number = (can_id >> 8) & 0x3FFFF
        self.priority = (can_id >> 26) & 0x7


class FrameFormat:
    CBFF    = 0     # classical          base       frame format
    CEFF    = 1     # classical          extended   frame format
    FBFF    = 2     # flexible data rate base       frame format
    FEFF    = 3     # flexible data rate extended   frame format