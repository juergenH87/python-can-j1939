import j1939
import logging

logger = logging.getLogger(__name__)

class DTC:
    """
    Parser for J1939 DTC (Diagnostic Trouble Code)
    """
    def __init__(self, dtc):
        self._spn = ((dtc & 0xFFFF) | ((dtc >> 5) & 0x70000))
        self._fmi = ((dtc >> 16) & 0x1F)
        self._oc = dtc & 0x7f
        self._cm = (dtc >> 7) & 0x01
        if self._cm != 0:
            logger.error("DM01: deprecated spn conversion modes are not supported")

    @property
    def spn(self):
        """
        :return:
            SPN Suspect Parameter Number

        :rtype: int
        """
        return self._spn

    @property
    def fmi(self):
        """
        :return:
            FMI Failure Mode Identifier

        :rtype: int
        """
        return self._fmi
        
    @property
    def occurrence_counter(self):
        """
        :return:
            DTC occurrence counter

        :rtype: int
        """
        return self._oc

    @property
    def conversion_mode(self):
        """
        :return:
            SPN conversion mode

        :rtype: int
        """
        return self._cm

class DiagnosticMessage1:
    """Diagnostic Messages 1

    Parser for J1939 Diagnostic Message 1

    :param data:
        j1939 pdu payload
    """

    def __init__(self, pgn, data):
        """
        :param data:
            PDU payload of normal (<= 8 Byte) or transport protocol message
        """
        if pgn != j1939.ParameterGroupNumber.PGN.DM01:
            return None

        self._data = data

        length = len(self._data)
        if length < 6:
            logger.error("DM01: length shorted than 6 bytes")
            return

        dtc_length = length - 2
        if (dtc_length % 4) != 0:
            logger.error("DM01: DTC length incorrect")
            return

        # calculate numboer of DTCs
        number_dtc = int(dtc_length / 4)

        # get lamp status
        self._lamp_status = {'pl light': self._data[0] & 0x01, 'awl light': (self._data[0] >> 1) & 0x01, 'rsl light': (self._data[0] >> 2) & 0x01, 'mil light': (self._data[0] >> 3) & 0x01,
                             'pl flash': self._data[0] & 0x01, 'awl flash': (self._data[0] >> 1) & 0x01, 'rsl flash': (self._data[0] >> 2) & 0x01, 'mil flash': (self._data[0] >> 3) & 0x01}

        # get DTC (Diagnostic Trouble Code)
        self._dtc_list = []
        for i in range(number_dtc):
            self._dtc_list.append( (self._data[i*4+2] & 0xff) 
                                | ((self._data[i*4+3] & 0xff) << 8)
                                | ((self._data[i*4+4] & 0xff) << 16) 
                                | ((self._data[i*4+5] & 0xff) << 24))

    @property
    def dtc_list(self):
        """
        :return:
            list to all DTCs included in DM1

        :rtype: list to int
        """
        return self._dtc_list

    @property
    def lamp_status(self):
        """
        :return:
            global lamp status for the DM1

        :rtype: dict: 'pl light', 'awl light', 'rsl light', 'mil light', 
                      'pl flash', 'awl flash', 'rsl flash', 'mil flash'
        """
        return self._lamp_status
    
