
from __future__ import annotations

import queue
import secrets
from collections.abc import Callable
from enum import Enum

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


class DM14Server:
    def __init__(self, ca: j1939.ControllerApplication) -> None:
        """
        performs memory access responses using DM14-DM18 messaging.
        :param obj ca: j1939 controller application
        """

        self._ca = ca
        self._busy = False
        self.sa: int | None = None
        self.state = ResponseState.IDLE
        self._key_from_seed: Callable[[int], int] | None = None
        self.data_queue: queue.Queue = queue.Queue()
        self._seed_generator: Callable[[], int] = self.generate_seed
        self._verify_key: Callable[..., bool] | None = None
        self.address: bytearray | None = None
        self.length = 8
        self.proceed = False
        self.data: bytearray | list = []
        self.error = 0x00
        self.edcp = 0x07
        self.status = j1939.Dm15Status.PROCEED.value
        self.direct = 0

    def _wait_for_data(self) -> None:
        """
        Determines whether to send data or wait to receive data based on the command type.
        If the command is a read command, then the data requested is sent.
        """
        if self.sa is None:
            raise RuntimeError("sa must be set before waiting for data")
        self._ca.subscribe(self._parse_dm16)
        self._send_dm15(
            self.length,
            self.direct,
            self.status,
            self.state,
            self.object_count,
            self.sa,
            j1939.ParameterGroupNumber.PGN.DM15,
            self.error,
            self.edcp,
        )

        if (
            self.command is j1939.Command.READ.value
            and self.state == ResponseState.SEND_PROCEED
        ):
            self._ca.unsubscribe(self._parse_dm16)
            self._send_dm16()
            if (len(self.data)) <= 8:
                self.proceed = True
                self.state = ResponseState.SEND_OPERATION_COMPLETE
                self._ca.subscribe(self.parse_dm14)
                self._send_dm15(
                    self.length,
                    self.direct,
                    self.status,
                    self.state,
                    self.object_count,
                    self.sa,
                    j1939.ParameterGroupNumber.PGN.DM15,
                    self.error,
                    self.edcp,
                )
        elif (
            self.command is j1939.Command.WRITE.value
            and self.state == ResponseState.SEND_PROCEED
        ):
            self.state = ResponseState.WAIT_FOR_DM16
        else:
            self._ca.unsubscribe(self._parse_dm16)
            self.state = ResponseState.IDLE
            self.sa = None

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
        if (
            (self.sa is not None and sa != self.sa)
            or (
                self.address is not None and self.address != data[2 : (self.length - 2)]
            )
            or self._busy
        ):
            self._send_dm15(
                self.length,
                data[1] >> 4,
                j1939.Dm15Status.OPERATION_FAILED.value,
                j1939.ResponseState.SEND_ERROR,
                data[0],
                sa,
                j1939.ParameterGroupNumber.PGN.DM15,
                self.error if self.error != 0x00 else 0x2,
                0x7,
            )
            self.set_busy(False)
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
                self.pointer_type = (data[1] >> 4) & 0x1
                self.object_count = data[0]
                self.access_level = (data[self.length - 1] << 8) + data[self.length - 2]
                self.data = data
                if self._key_from_seed is not None:
                    self.state = ResponseState.WAIT_FOR_KEY
                    self._pgn = j1939.ParameterGroupNumber.PGN.DM15
                    self._send_dm15(
                        self.length,
                        self.direct,
                        self.status,
                        self.state,
                        self.object_count,
                        sa,
                    )
                else:
                    self.state = ResponseState.SEND_PROCEED

            case ResponseState.WAIT_FOR_KEY:
                self.length = len(data)
                self.address = data[2 : (self.length - 2)]
                self.command = ((data[1] - 1) & 0x0F) >> 1
                self.object_count = data[0]
                self.key = (data[self.length - 1] << 8) + data[self.length - 2]
                self.data = data
                self.state = ResponseState.SEND_PROCEED

            case ResponseState.WAIT_OPERATION_COMPLETE:
                self.reset_server()

            case _:
                self.reset_server()
                raise ValueError("Invalid state")

    def _send_dm15(
        self,
        length: int,
        direct: int,
        status: int,
        state: ResponseState,
        object_count: int,
        sa: int,
        pgn: int = 55296, # FIXME: we should use constants, like we used to: j1939.ParameterGroupNumber.PGN.DM15, but we get into circular imports errors. https://github.com/RaulSMS/python-can-j1939/issues/24
        error: int | None = None,
        edcp: int | None = None,

    ) -> None:
        """
        Send DM15 message to device, used to send the proceed message,
        the generated seed, or the operation complete message
        :param int length: length of data
        :param int direct: value of direct transaction or not
        :param int status: status of operation
        :param ResponseState state: state of operation
        :param int object_count: amount of objects to read
        :param int sa: source address
        :param int pgn: pgn value
        :param int error: error code if necessary
        :param int edcp: value of edcp for transaction
        """
        self._pgn = j1939.ParameterGroupNumber.PGN.DM15
        data = [0xFF] * length
        data[1] = (direct << 4) + (status << 1) + 1
        match state:
            case ResponseState.WAIT_FOR_KEY:
                self.seed = self._seed_generator()
                data[0] = 0x00
                data[length - 2] = self.seed & 0xFF
                data[length - 1] = self.seed >> 8

            case ResponseState.SEND_PROCEED:
                data[0] = object_count

            case ResponseState.SEND_OPERATION_COMPLETE:
                self.command = j1939.Command.OPERATION_COMPLETED.value
                data[0] = 0x00
                data[1] = (direct << 4) + (self.command << 1) + 1
                self.state = ResponseState.WAIT_OPERATION_COMPLETE

            case ResponseState.SEND_ERROR:
                if error is None:
                    raise RuntimeError("error must be provided for SEND_ERROR state")
                if edcp is None:
                    raise RuntimeError("edcp must be provided for SEND_ERROR state")
                status = j1939.Dm15Status.OPERATION_FAILED.value
                data[0] = 0x00
                data[1] = (direct << 4) + (status << 1) + 1
                data[length - 6] = error & 0xFF
                data[length - 5] = (error >> 8) & 0xFF
                data[length - 4] = error >> 16
                data[length - 3] = edcp

            case _:
                self.reset_server()
                raise ValueError("Invalid state")
        self._ca.send_pgn(0, (pgn >> 8) & 0xFF, sa & 0xFF, 6, data)

    def _send_dm16(self) -> None:
        """
        Send DM16 message to device, used to send requested data
        """
        if self.sa is None:
            raise RuntimeError("sa must be set before sending DM16")
        self._pgn = j1939.ParameterGroupNumber.PGN.DM16
        data = []
        byte_count = len(self.data)
        data.append(0xFF if byte_count > 7 else byte_count)
        for i in range(byte_count):
            data.append(self.data[i])

        data.extend([0xFF] * (self.length - byte_count - 1))
        if byte_count > 8:
            self._ca.subscribe(self._parse_dm16)
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
        self.data_queue.put(data[1 : length + 1])
        self._ca.unsubscribe(self._parse_dm16)
        self._ca.subscribe(self.parse_dm14)
        self.state = ResponseState.SEND_OPERATION_COMPLETE

        self._send_dm15(
            self.length,
            self.direct,
            self.status,
            self.state,
            self.object_count,
            sa,
        )

    def bytes_to_int(self, data: bytearray) -> int:
        """
        Convert bytearray to integer
        :param bytearray data: bytearray to be converted to integer
        """
        return int.from_bytes(data, byteorder="little", signed=False)

    def set_busy(self, busy: bool) -> None:
        """
        Sets busy variable to indicate if busy or not
        :param busy: busy value
        """
        self._busy = busy

    def generate_seed(self) -> int:
        """
        Generte a random seed value for key generation
        """
        seed = secrets.randbits(16)
        if (seed == 0xFFFF) or (seed == 0x0000):
            seed = 0xBEEF
        return seed

    def set_seed_key_algorithm(self, algorithm: Callable[[int], int]) -> None:
        """
        Set seed key algorithm to be used for key generation
        :param algorithm: seed-key algorithm
        """
        self._key_from_seed = algorithm

    def set_seed_generator(self, algorithm: Callable[[], int]) -> None:
        """
        Sets seed generation algorithm to be used for generating a seed value
        :param algorithm: seed generation algorithm
        """
        self._seed_generator = algorithm

    def set_verify_key(self, algorithm: Callable[..., bool]) -> None:
        """
        Set key verification algorithm to be used for key verification
        :param algorithm: key verification algorithm
        """
        self._verify_key = algorithm

    def verify_key(self, seed: int, key: int) -> bool:
        """
        Checks to see if key is valid
        :param int seed: seed
        :param int key: key
        """
        if self._verify_key is not None:
            # TODO: add ability to dynamically pass arguments to verification function if needed,
            # if this is breaking can just add **kwargs to function defintion used to set the verification function
            # this will allow for the reception of additional arguments if needed
            if self.address is None:
                raise RuntimeError("address must be set before verifying key")
            return self._verify_key(
                seed=seed, key=key, address=self.bytes_to_int(self.address), sa=self.sa
            )
        if self._key_from_seed is None:
            raise RuntimeError("no key-from-seed algorithm set; call set_seed_key_algorithm first")
        return self._key_from_seed(seed) == key

    def unsubscribe_all(self) -> None:
        """
        Unsubscribes all message handlers
        """
        self._ca.unsubscribe(self.parse_dm14)
        self._ca.unsubscribe(self._parse_dm16)

    def reset_server(self) -> None:
        """
        Resets server to remove transaction specific data
        """
        self.state = ResponseState.IDLE
        self.data_queue = queue.Queue()
        self.sa = None
        self.seed = None
        self.key = None
        self._busy = False
        self.address = None
        self.length = 8
        self.proceed = False
        self.data = []
        self.error = 0x00
        self.edcp = 0x07
        self.status = j1939.Dm15Status.PROCEED.value
        self.direct = 0
        self.unsubscribe_all()

    def respond(
        self,
        proceed: bool,
        data=None,
        error: int = 0xFFFFFF,
        edcp: int = 0xFF,
        max_timeout: int = 3,
    ) -> list | None:
        """
        Respond to DM14 query with the requested data or confimation of operation is good to proceed
        :param bool proceed: whether the operation is good to proceed
        :param list data: data to be sent to device
        :param int error: error code to be sent to device
        :param int edcp: value for edcp extension
        :param int max_timeout: max time for transaction
        """
        if data is None:
            data = []
        self.proceed = proceed
        self.data = data
        self.error = error
        self.edcp = edcp
        self.status = (
            j1939.Dm15Status.PROCEED.value
            if proceed
            else j1939.Dm15Status.OPERATION_FAILED.value
        )
        if self.status == j1939.Dm15Status.PROCEED.value:
            self.state = ResponseState.SEND_PROCEED
        else:
            self.state = ResponseState.SEND_ERROR
        self._wait_for_data()
        mem_data: list | None = None
        if self.state == ResponseState.WAIT_FOR_DM16:
            try:
                mem_data = self.data_queue.get(block=True, timeout=max_timeout)
            except queue.Empty:
                self.reset_server()
                raise RuntimeError("No data received from DM16 within timeout period")
        return mem_data
