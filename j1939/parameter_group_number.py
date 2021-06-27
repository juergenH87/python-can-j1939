import j1939

class ParameterGroupNumber:
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

    class PGN:
        FEFF_MULTI_PG       =  9472  # 2500
        FD_TP_CM            = 19712  # 4D00
        FD_TP_DT            = 19968  # 4E00

        REQUEST             = 59904  # EA00
        #ACKNOWLEDGEMENT    = 59392
        ADDRESSCLAIM        = 60928  # EE00
        DATATRANSFER        = 60160  # EB00
        TP_CM               = 60416  # EC00
        #COMMANDED_ADDRESS  = 65240
        #PROPRIETARY_A      = 61184
        #SOFTWARE_IDENT     = 65242
        # Diagnostic messages
        DM01	            = 65226  # FECA
        DM02	            = 65227  # FECB
        DM03	            = 65228  # FECC
        DM04	            = 65229  # FECD
        DM05	            = 65230  # FECE
        DM06	            = 65231  # FECF
        DM07	            = 58112  # E300
        DM08	            = 65232  # FED0
        DM10                = 65234  # FED2
        DM11                = 65235  # FED3
        DM12                = 65236  # FED4
        DM13                = 57088  # DF00
        DM14                = 55552  # D900
        DM15                = 55296  # D800
        DM16                = 55040  # D700
        DM17                = 54784  # D600
        DM18                = 54272  # D400
        DM19                = 54016  # D300
        DM20                = 49664  # C200
        DM21                = 49408  # C100
        DM22                = 49920  # C300
        DM23                = 64949  # FDB5
        DM24                = 64950  # FDB6
        DM25                = 64951  # FDB7
        DM26                = 64952  # FDB8
        DM27                = 64898  # FD82
        DM28                = 64896  # FD80
        DM29                = 40448  # 9E00
        DM30                = 41984  # A400
        DM31                = 41728  # A300
        DM32                = 41472  # A200
        DM33                = 41216  # A100
        DM34                = 40960  # A000
        DM35                = 40704  # 9F00
        DM36                = 64868  # FD64
        DM37                = 64867  # FD63
        DM38                = 64866  # FD62
        DM39                = 64865  # FD61
        DM40                = 64864  # FD60
        DM41                = 64863  # FD5F
        DM42                = 64862  # FD5E
        DM43                = 64861  # FD5D
        DM44                = 64860  # FD5C
        DM45                = 64859  # FD5B
        DM46                = 64858  # FD5A
        DM47                = 64857  # FD59
        DM48                = 64856  # FD58
        DM49                = 64855  # FD57
        DM50                = 64854  # FD56
        DM51                = 64853  # FD55
        DM52                = 64852  # FD54
        DM53                = 64721  # FCD1
        DM54                = 64722  # FCD2
        DM55                = 64723  # FCD3
        DM56                = 64711  # FCC7
        DM57                = 64710  # FCC6

    class Address:
        NULL                = 254
        GLOBAL              = 255

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
