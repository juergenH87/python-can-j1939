from enum import Enum
import queue
import secrets
import j1939


class ResponseState(Enum):
    IDLE = 1
    WAIT_FOR_DM14 = 2
    WAIT_FOR_KEY = 3
    SEND_PROCEED = 4
    SEND_OPERATION_COMPLETE = 5
    WAIT_OPERATION_COMPLETE = 6
    SEND_ERROR = 7
    WAIT_FOR_DM16 = 8


class DM14Response:
    def __init__(self, ca: j1939.ControllerApplication) -> None:
        """
        performs memory access responses using DM14-DM18 messaging.

        :param obj ca: j1939 controller application
        """

        self._ca = ca
        self.sa = None
        self.state = ResponseState.IDLE
        self._key_from_seed = None
        self.data_queue = queue.Queue()
        self.mem_data = None
        self._seed_generator = self.generate_seed

    def _wait_for_data(self) -> None:
        """
        Determines whether to send data or wait to receive data based on the command type.
        If the command is a read command, then the data requested is sent.
        """
        if self.command is j1939.Command.READ.value:
            self._send_dm15()
            self._send_dm16()
            self.proceed = True
            self.state = ResponseState.SEND_OPERATION_COMPLETE
            self._ca.subscribe(self.parse_dm14)
            self._send_dm15()
        else:
            self._ca.subscribe(self._parse_dm16)
            self._send_dm15()
            self.state = ResponseState.WAIT_FOR_DM16

    def parse_dm14(
        self, priority: int, pgn: int, sa: int, timestamp: int, data: bytearray
    ) -> None:
        """
        parse DM14 message received
        :param int priority: priority of the message
        :param int pgn: parameter group number of the message
        :param int sa: source address of the message
        :param int timestamp: timestamp of the message
        :param bytearray data: data of the PDU
        """
        if pgn != j1939.ParameterGroupNumber.PGN.DM14:
            return
        if self.sa is not None and sa != self.sa:
            return
        self.length = len(data)
        self.direct = data[1] >> 4
        match self.state:
            case ResponseState.IDLE:
                self.pgn = pgn
                self.sa = sa
                self.status = j1939.Dm15Status.PROCEED.value
                self.address = data[2 : (self.length - 2)]
                self.direct = data[1] >> 4
                self.command = ((data[1] - 1) & 0x0F) >> 1
                self.object_count = data[0]
                self.access_level = (data[self.length - 1] << 8) + data[self.length - 2]
                self.data = data
                if self._key_from_seed is not None:
                    self.state = ResponseState.WAIT_FOR_KEY
                    self._send_dm15()
                else:
                    self.state = ResponseState.SEND_PROCEED

            case ResponseState.WAIT_FOR_KEY:
                self.length = len(data)
                self.address = data[2 : (self.length - 2)]
                self.command = ((data[1] - 1) & 0x0F) >> 1
                self.object_count = data[0]
                self.key = (data[self.length - 1] << 8) + data[self.length - 2]
                self.data = data

            case ResponseState.WAIT_OPERATION_COMPLETE:
                self.state = ResponseState.IDLE
                self.sa = None
                self._ca.unsubscribe(self.parse_dm14)

            case _:
                print("Invalid state")

    def _send_dm15(self) -> None:
        """
        Send DM15 message to device, used to send the proceed message,
        the generated seed, or the operation complete message
        """
        self._pgn = j1939.ParameterGroupNumber.PGN.DM15
        data = [0xFF] * self.length
        data[1] = (self.direct << 4) + (self.status << 1) + 1
        match self.state:
            case ResponseState.WAIT_FOR_KEY:
                self.seed = self._seed_generator()
                print(self.seed)
                data[0] = 0x00
                data[self.length - 2] = self.seed & 0xFF
                data[self.length - 1] = self.seed >> 8
            case ResponseState.SEND_PROCEED:
                data[0] = self.object_count
            case ResponseState.SEND_OPERATION_COMPLETE:
                self.command = j1939.Command.OPERATION_COMPLETED.value
                data[0] = 0x00
                data[1] = (self.direct << 4) + (self.command << 1) + 1
                self.state = ResponseState.WAIT_OPERATION_COMPLETE
            case ResponseState.SEND_ERROR:
                self.status = j1939.Dm15Status.OPERATION_FAILED.value
                data[0] = 0x00
                data[1] = (self.direct << 4) + (self.status << 1) + 1
                data[self.length - 6] = self.error & 0xFF
                data[self.length - 5] = (self.error >> 8) & 0xFF
                data[self.length - 4] = self.error >> 16
                data[self.length - 3] = self.edcp
            case _:
                raise ValueError("Invalid state")
        self._ca.send_pgn(0, (self._pgn >> 8) & 0xFF, self.sa & 0xFF, 6, data)

    def _send_dm16(self) -> None:
        """
        Send DM16 message to device, used to send requested data
        """
        self._pgn = j1939.ParameterGroupNumber.PGN.DM16
        data = []
        byte_count = len(self.data)
        data.append(0xFF if byte_count > 7 else byte_count)
        for i in range(byte_count):
            data.append(self.data[i])
        data.extend([0xFF] * (self.length - byte_count - 1))
        self._ca.send_pgn(0, (self._pgn >> 8) & 0xFF, self.sa & 0xFF, 7, data)

    def _parse_dm16(
        self, priority: int, pgn: int, sa: int, timestamp: int, data: bytearray
    ) -> None:
        """
        parse DM16 message received, used to parse data received write command
        :param int priority: priority of the message
        :param int pgn: parameter group number of the message
        :param int sa: source address of the message
        :param int timestamp: timestamp of the message
        :param bytearray data: data of the PDU
        """

        if pgn != j1939.ParameterGroupNumber.PGN.DM16 or sa != self.sa:
            return
        length = min(data[0], len(data) - 1)
        # assert object_count == self.object_count
        self.mem_data = data[1 : length + 1]
        self.data_queue.put(data)
        self._ca.unsubscribe(self._parse_dm16)
        self._ca.subscribe(self.parse_dm14)
        self.state = ResponseState.SEND_OPERATION_COMPLETE
        self._send_dm15()

    def bytes_to_int(self, data: bytearray) -> int:
        """
        Convert bytesaray to integer
        :param bytearray data: bytearray to be converted to integer
        """
        return int.from_bytes(data, byteorder="little", signed=False)

    def generate_seed(self) -> int:
        """
        Generte a random seed value for key generation
        """
        seed = secrets.randbits(16)
        if (seed == 0xFFFF) or (seed == 0x0000):
            seed = 0xBEEF
        return seed

    def set_seed_key_algorithm(self, algorithm: callable) -> None:
        """
        Set seed key algorithm to be used for key generation
        :param callable algorithm: seed-key algorithm
        """
        self._key_from_seed = algorithm

    def set_seed_generator(self, algorithm: callable) -> None:
        """
        Sets seed generation algorithm to be used for generating a seed value
        :param callable algorithm: seed generation algorithm
        """
        self._seed_generator = algorithm

    def respond(
        self,
        proceed: bool,
        data=None,
        error: int = 0xFFFFFF,
        edcp: int = 0xFF,
    ) -> list:
        """
        Respond to DM14 query with the requested data or confimation of operation is good to proceed
        :param bool proceed: whether the operation is good to proceed
        :param list data: data to be sent to device
        :param int error: error code to be sent to device
        :param int edcp: value for edcp extension
        """
        if data is None:
            data = []
        self.proceed = proceed
        self.data = data
        self.error = error
        self.edcp = edcp
        self.status = (
            j1939.Dm15Status.PROCEED.value if proceed else j1939.Dm15Status.OPERATION_FAILED.value
        )
        if self.status == j1939.Dm15Status.PROCEED.value:
            self.state = ResponseState.SEND_PROCEED
        else:
            self.state = ResponseState.SEND_ERROR
        # self._ca.unsubscribe(self._parse_dm14)
        self._wait_for_data()
        mem_data = None
        if self.state == ResponseState.WAIT_FOR_DM16:
            mem_data = self.data_queue.get(block=True, timeout=3)

        return self.mem_data if self.mem_data is not None else None
