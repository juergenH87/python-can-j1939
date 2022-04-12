import j1939
import logging

logger = logging.getLogger(__name__)

class DTC:
    """
    Parser for J1939 DTC (Diagnostic Trouble Code)
    """
    def __init__(self, dtc=None, spn=None, fmi=None, oc=0):
        if dtc != None:
            self._dtc = dtc
            self._spn = ((dtc & 0xFFFF) | ((dtc >> 5) & 0x70000))
            self._fmi = ((dtc >> 16) & 0x1F)
            self._oc  = ((dtc >> 24) & 0x7f)
            self._cm  = ((dtc >> 31) & 0x01)
            if self._cm != 0:
                logger.error("DM01: deprecated spn conversion modes are not supported")
        else:
            self._dtc = ((spn & 0xFFFF) | ((spn & 0x70000) << 5) | ((fmi & 0x1F) << 16) | ((oc & 0x7F) << 24))
            self._spn = spn
            self._fmi = fmi
            self._oc = oc
            self._cm = 0

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
    def oc(self):
        """
        :return:
            DTC occurrence counter

        :rtype: int
        """
        return self._oc

    @property
    def cm(self):
        """
        :return:
            SPN conversion mode

        :rtype: int
        """
        return self._cm

    @property
    def dtc(self):
        """
        :return:
            DTC Diagnostic Trouble Code

        :rtype: int
        """
        return self._dtc

class DtcLamp:
    """Diagnostic trouble code lamp status
    """
    OFF            = 0
    ON             = 1
    ON_SLOW_FLASH  = 2
    ON_FAST_FLASH  = 3
    NA             = 4

    _KEYS = ['pl', 'awl', 'rsl', 'mil']
    _DATA_LUT = {OFF: [0,3], ON: [1,3], ON_SLOW_FLASH: [1,0], ON_FAST_FLASH: [1,1], NA: [3,3]}

    def get_status(self, lamp, flash):
        status = self.NA
        if lamp == 0:
            status = self.OFF
        elif lamp == 1:
            if flash == 0:
                status = self.ON_SLOW_FLASH
            elif flash == 1:
                status = self.ON_FAST_FLASH
            elif flash == 3:
                status = self.ON
        return status

    def get_data(self, status_dic):
        data = [0]*2
        for idx, lamp_key in enumerate(self._KEYS):
            # initialize not available lamps
            if status_dic.get(lamp_key) == None:
                status_dic[lamp_key] = DtcLamp.OFF
            elif status_dic[lamp_key] not in self._DATA_LUT:
                status_dic[lamp_key] = DtcLamp.OFF
                logger.error("Lamp status n/a")
            lamp, flash = self._DATA_LUT[status_dic[lamp_key]]

            data[0] |= (lamp  << (idx*2))
            data[1] |= (flash << (idx*2))

        return data


class Dm1:
    """Active Diagnostic Trouble Codes (DM1)

    Parser for DM1

    DM1 provides diagnostic lamp status and diagnostic trouble codes (DTCs).
    Together, the lamp and DTC information convey the diagnostic condition
    of the transmitting electronic component to other components on the network.
    Occurrence counts may be provided.
    """
    _msg_subscriber_added = False

    def __init__(self, ca: j1939.ControllerApplication):
        """
        :param obj ca: j1939 controller application
        """
        self._pgn = j1939.ParameterGroupNumber.PGN.DM01
        self._lamp_status = {}
        self._dtc_dic_list = []
        self._data = []
        self._subscribers = []
        self._ca = ca

    def subscribe(self, callback):
        """Add the given callback to the Dm1 message notification stream.

        :param callback:
            Function to call when Dm1 message is received.
        """
        if self._msg_subscriber_added == False:
            self._ca.subscribe(self._receive)
            self._msg_subscriber_added = True

        self._subscribers.append(callback)

    def unsubscribe(self, callback):
        """Stop listening for Dm1 message.

        :param callback:
            Function to call when Dm1 message is received.
        """
        self._subscribers.remove(callback)

    def start_send(self, callback, cycletime=1):
        """Start cyclic sending of Dm1 message

        :param callback:
            Function to call before Dm1 message is sent
        :param int cycletime:
            Optional send cycletime
            cycletime is 1s if not specified
        :param int priority:
            priority of Dm1 message
        """
        cookie = {'cb': callback,}
        self._ca.add_timer(delta_time=cycletime, callback=self._send, cookie=cookie)

    def stop_send(self, callback):
        self._ca.remove_timer(callback)

    @property
    def dtc_dic_list(self):
        """
        :return:
            list of dictionaries of all DTCs included in DM1

        :rtype: list of dic: 'spn', 'fmi', 'oc'
        """
        return self._dtc_dic_list

    @property
    def lamp_status(self):
        """
        :return:
            global lamp status for the DM1

        :rtype: dic: 'pl', 'awl', 'rsl', 'mil'
        """
        return self._lamp_status

    @property
    def data(self):
        """
        :return:
            j1939 pdu payload

        :rtype: list of int
        """
        return self._data

    def _receive(self, priority, pgn, sa, timestamp, data):
        if pgn == self._pgn:
            self._data = data
            self._parse_dm1_receive_data()
            self._notify_subscribers(sa, timestamp)

    def _send(self, cookie):
        # get dm1 data
        self._lamp_status, self._dtc_dic_list = cookie['cb']()

        # create payload - lamp status
        self._data = DtcLamp().get_data(self._lamp_status)

        # create payload - dtc
        for dtc_dic in self._dtc_dic_list:
            # not optional arguments
            if dtc_dic.get('spn') == None:
                continue
            if dtc_dic.get('fmi') == None:
                continue
            # optional arguments
            if dtc_dic.get('oc') == None:
                dtc_dic['oc'] = 0

            dtc = DTC(spn=dtc_dic['spn'], fmi=dtc_dic['fmi'], oc=dtc_dic['oc']).dtc
            self._data.append(dtc & 0xFF)
            self._data.append((dtc >> 8) & 0xFF)
            self._data.append((dtc >> 16) & 0xFF)
            self._data.append((dtc >> 24) & 0xFF)

        # Default Priority: 6
        # priority should be 7 when transport protocol is used (SAE J1939-21 requirement)
        if len(self._data) > 8:
            priority = 7
        else:
            priority = 6
        # send pgn
        self._ca.send_pgn(0, (self._pgn >> 8) & 0xFF, self._pgn & 0xFF, priority, self._data )

        # returning true keeps the timer event active
        return True

    def _parse_dm1_receive_data(self):
        length = len(self._data)
        if length < 6:
            logger.error("DM01: length shorted than 6 bytes")
            return

        dtc_length = length - 2
        if (length != 8) and (dtc_length % 4) != 0:
            logger.error("DM01: DTC length incorrect")
            return

        # calculate numboer of DTCs
        number_dtc = int(dtc_length / 4)

        # get lamp status
        self._lamp_status['pl']  = DtcLamp().get_status( self._data[0] & 0x03,        self._data[1] & 0x03)
        self._lamp_status['awl'] = DtcLamp().get_status((self._data[0] >> 2) & 0x03, (self._data[1] >> 2) & 0x03)
        self._lamp_status['rsl'] = DtcLamp().get_status((self._data[0] >> 4) & 0x03, (self._data[1] >> 4) & 0x03)
        self._lamp_status['mil'] = DtcLamp().get_status((self._data[0] >> 6) & 0x03, (self._data[1] >> 6) & 0x03)

        # get DTC (Diagnostic Trouble Code)
        self._dtc_dic_list = []
        for i in range(number_dtc):
            dtc_int = ( (self._data[i*4+2] & 0xff)
                     | ((self._data[i*4+3] & 0xff) << 8)
                     | ((self._data[i*4+4] & 0xff) << 16)
                     | ((self._data[i*4+5] & 0xff) << 24))

            dtc = DTC(dtc=dtc_int)
            self._dtc_dic_list.append( {'spn': dtc.spn, 'fmi': dtc.fmi, 'oc': dtc.oc } )

    def _notify_subscribers(self, sa, timestamp):
        for callback in self._subscribers:
            callback(sa, self.lamp_status.copy(), self._dtc_dic_list.copy(), timestamp)


class Dm11:
    """Diagnostic Data Clear/Reset for Active DTCs (DM11)
    """
    def __init__(self, ca: j1939.ControllerApplication):
        """
        :param obj ca: j1939 controller application
        """
        self._pgn = j1939.ParameterGroupNumber.PGN.DM11
        self._ca = ca
        self._subscribers_req_clear = []
        self._subscribers_ack_clear = []
        ca.subscribe_request(self._on_request)
        ca.subscribe_acknowledge(self._on_acknowledge)

    def request_clear_all(self, destination):
        self._ca.send_request(0, self._pgn, destination)

    def subscribe_request_clear_all(self, callback):
        self._subscribers_req_clear.append(callback)

    def subscribe_acknowledge_clear_all(self, callback):
        self._subscribers_ack_clear.append(callback)

    def _on_request(self, src_address, dest_address, pgn):
        for subscriber in self._subscribers_req_clear:
            subscriber(src_address, dest_address, pgn)
            # TODO: send acknowledge

    def _on_acknowledge(self, src_address, dest_address, pgn):
        for subscriber in self._subscribers_ack_clear:
            # TODO
            pass

class Dm22:
    """Individual Clear/Reset of Active and Previously Active DTC (DM22)
    """
    class DTC_CLR_CTRL:
        """Individual DTC Clear/Reset Control Byte
        """
        PA_REQ   =  1 # Request to clear/reset a specific previously active DTC
        PA_ACK   =  2 # Positive acknowledge of clear/reset of a specific previously active DTC
        PA_NACK  =  3 # Negative acknowledge of clear/reset of a specific previously active DTC
        ACT_REQ  = 17 # Request to clear/reset a specific active DTC
        ACT_ACK  = 18 # Positive acknowledge of clear/reset of a specific active DTC
        ACT_NACK = 19 # Negative acknowledge of clear/reset of a specific active DTC

    class DTC_CLR_CTRL_SPECIFIC:
        """Control Byte Specific Indicator for Individual DTC Clear
        """
        GENERAL_NACK        = 0
        ACCESS_DENIED       = 1
        DTC_UNKNOWN         = 2
        DTC_PA_NOT_ACTIVE   = 3
        DTC_ACT_NOT_ACTIVE  = 4

    def __init__(self, ca: j1939.ControllerApplication):
        """
        :param obj ca: j1939 controller application
        """
        self._pgn = j1939.ParameterGroupNumber.PGN.DM22
        self._ca = ca

    def request_clear_act_dtc(self, dest_address, spn, fmi):
        """Request to Clear/Reset Active DTC

        :param dest_address:
            destination address of the node
        :param spn:
            spn of the dtc to be cleared
        :param spn:
            fmi of the dtc to be cleared
        """
        self._send_request(self.DTC_CLR_CTRL.ACT_REQ, dest_address, fmi, spn)

    def request_clear_pa_dtc(self, dest_address, spn, fmi):
        """Request to Clear/Reset Previously Active DTC

        :param dest_address:
            destination address of the node
        :param spn:
            spn of the dtc to be cleared
        :param spn:
            fmi of the dtc to be cleared
        """
        self._send_request(self.DTC_CLR_CTRL.PA_REQ, dest_address, fmi, spn)

    def _send_request(self, control_byte, dest_address, fmi, spn):
        data = [0xFF]*8
        data[0] = control_byte
        data[5] = spn & 0xFF
        data[6] = (spn >> 8) & 0xFF
        data[7] = ((spn >> 22) & 0xE0) | (fmi & 0x1F)

        # send pgn
        self._ca.send_pgn(0, (self._pgn >> 8) & 0xFF, dest_address & 0xFF, 6, data)