
import j1939

class ParameterGroupNumber(object):
    """Parameter Group Number (PGN).
    
    The PGN are described in SAE J1939/21 and consists of four parts:
      * 1-bit Reserved (sometimes referred to as Extended Data Page)
      * 1-bit Data Page (DP)
      * 8-bit PDU Format (PF)
      * 8-bit PDU Specific (PS)

    Predefined PGNs are listed in SAE J1939 and SAE J1939/71

    A PF value from 0 to 239 (PDU1) indicates a destination address (DA) in PS 
    (peer-to-peer communication). A PF value from 240 to 255 (PDU2) indicates
    a Group Extension (GE) inside the PS (broadcast message).
    The DA 255 is called the Global Destination Address. It requires all nodes 
    to listen to and to respond, if required.

    TODO: naming/wording: according the standard, a PGN in PDU1 format always
          sets the 8 Bit PS to 0.
          Do we have to separate this object to reflect this rule. And if we 
          have to, how to name the other PGN object?
    """

    class PGN(object):
        #TODO:
        REQUEST = 59904               # EA00
        #ACKNOWLEDGEMENT = 59392
        ADDRESSCLAIM = 60928          # EE00
        DATATRANSFER = 60160          # EB00
        TP_CM = 60416                 # EC00
        #COMMANDED_ADDRESS = 65240
        #PROPRIETARY_A = 61184
        #SOFTWARE_IDENT = 65242

    class Address(object):
        NULL = 254
        GLOBAL = 255

    def __init__(self, data_page=0, pdu_format=0, pdu_specific=0):
        """
        :param data_page:
            1-bit Data Page
        :param pdu_format:
            8-bit PDU Format
        :param pdu_specific:
            8-bit PDU Specific
        """
        self.data_page = data_page & 0x01
        self.pdu_format = pdu_format & 0xFF
        self.pdu_specific = pdu_specific & 0xFF

    @property
    def is_pdu1_format(self):
        """Indicates Peer-to-Peer communication"""
        return True if self.pdu_format>=0 and self.pdu_format<=239 else False

    @property
    def is_pdu2_format(self):
        """Indicates broadcast communication"""
        return True if self.pdu_format>=240 and self.pdu_format<=255 else False
        
    def from_message_id(self, mid):
        """Fills in the object from a MessageId given"""
        if not isinstance(mid, j1939.MessageId):
            raise ValueError("the parameter mid must be an instance of MessageId") 

        self.data_page = (mid.parameter_group_number >> 16) & 0x01
        self.pdu_format = (mid.parameter_group_number >> 8) & 0xFF
        self.pdu_specific = mid.parameter_group_number & 0xFF

    @property
    def value(self):
        """Returns the value of the PGN"""
        return (self.data_page << 16) | (self.pdu_format << 8) | self.pdu_specific 

            