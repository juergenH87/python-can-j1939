from enum import Enum
import queue
import j1939


class QueryState(Enum):
    IDLE = 1
    WAIT_FOR_SEED = 2
    WAIT_FOR_DM16 = 3
    WAIT_FOR_OPER_COMPLETE = 4


class Command(Enum):
    ERASE = 0
    READ = 1
    WRITE = 2
    STATUS_REQUEST = 3
    OPERATION_COMPLETED = 4
    OPERATION_FAILED = 5
    BOOT_LOAD = 6
    EDCP_GENERATION = 7


class Dm15Status(Enum):
    PROCEED = 0
    BUSY = 1
    OPERATION_COMPLETE = 4
    OPERATION_FAILED = 5


class Dm14Query:
    def __init__(self, ca: j1939.ControllerApplication) -> None:
        """
        performs memory access queries using DM14-DM18 messaging.  Presently only read and write queries are supported

        :param obj ca: j1939 controller application
        """

        self._ca = ca
        self.state = QueryState.IDLE
        self._seed_from_key = None
        self.data_queue = queue.Queue()
        self.mem_data = None
        self.exception_queue = queue.Queue()

    def _wait_for_data(self) -> None:
        """
        Determines whether to send data or wait to receive data based on the command type. If the command is a write command, then the data is sent.
        If the command is a read command, then the device waits to receive data.
        """
        assert self.state is QueryState.WAIT_FOR_SEED
        if self.command is Command.WRITE:
            self.state = QueryState.WAIT_FOR_OPER_COMPLETE
            self._send_dm16()
        else:
            self.state = QueryState.WAIT_FOR_DM16
            self._ca.unsubscribe(self._parse_dm15)
            self._ca.subscribe(self._parse_dm16)

    def _send_operation_complete(self) -> None:
        """
        Send DM14 message to confirm the operation is complete
        """
        self.object_count = 1
        self.command = Command.OPERATION_COMPLETED
        self._send_dm14(0xFFFF)

    def _send_dm14(self, key_or_user_level: int) -> None:
        """
        Send DM14 message to device, used to initialize a memory access operation,
        respond with a key when needed, and to confirm the operation is complete

        :param int key_or_user_level: key or user level
        """
        self._pgn = j1939.ParameterGroupNumber.PGN.DM14
        pointer = self.address.to_bytes(length=4, byteorder="little")
        data = []
        data.append(self.object_count & 0xFF)
        data.append(
            ((self.object_count >> 3) & 0xE0) + (self.direct << 4) + (self.command.value << 1) + 1
        )  # (SAE reserved = 1)
        for octet in pointer:
            data.append(octet)
        data.append(key_or_user_level & 0xFF)
        data.append(key_or_user_level >> 8)
        self._ca.send_pgn(
            0, (self._pgn >> 8) & 0xFF, self._dest_address & 0xFF, 6, data
        )

    def _send_dm16(self) -> None:
        """
        Send DM16 message to device, used to send data to the device
        """
        self._pgn = j1939.ParameterGroupNumber.PGN.DM16
        data = []
        byte_count = len(self.bytes)
        data.append(0xFF if byte_count > 7 else byte_count)
        data.extend(self.bytes)
        self._ca.send_pgn(
            0, (self._pgn >> 8) & 0xFF, self._dest_address & 0xFF, 6, data
        )

    def _parse_dm15(
        self, priority: int, pgn: int, sa: int, timestamp: int, data: bytearray
    ) -> None:
        """
        Parse DM15 message from device, used to determine whether device is ready, or if operation has completed and to receive seed from device
        :param int priority: priority of the message
        :param int pgn: parameter group number of the message
        :param int sa: source address of the message
        :param int timestamp: timestamp of the message
        :param bytearray data: data of the PDU
        """
        if pgn != j1939.ParameterGroupNumber.PGN.DM15 or sa != self._dest_address:
            return
        status = (data[1] >> 1) & 7
        if (
            status is Dm15Status.BUSY.value
            or status is Dm15Status.OPERATION_FAILED.value
        ):
            error = int.from_bytes(data[2:5], byteorder="little", signed=False)
            edcp = data[5]
            self.data_queue.put(None)
            if edcp == 0x06 or edcp == 0x07:
                if error in j1939.ErrorInfo:
                    self.exception_queue.put(
                        RuntimeError(
                            f"Device {hex(sa)} error: {hex(error)} {j1939.ErrorInfo[error]} edcp: {hex(edcp)}"
                        )
                    )
                else:
                    self.exception_queue.put(
                        RuntimeError(
                            f"Device {hex(sa)} error: {hex(error)} edcp: {hex(edcp)}"
                        )
                    )
        else:
            seed = (data[7] << 8) + data[6]
            length = data[0] + ((data[1] & 0xE0) << 3)
            if seed == 0xFFFF and length == self.object_count:
                self._wait_for_data()
            else:
                if self.state is QueryState.WAIT_FOR_OPER_COMPLETE:
                    assert status is Command.OPERATION_COMPLETED.value
                    self.state = QueryState.IDLE
                    self._send_operation_complete()
                    self.data_queue.put(self.mem_data)
                else:
                    assert self.state is QueryState.WAIT_FOR_SEED
                    if self._seed_from_key is not None:
                        self._send_dm14(self._seed_from_key(seed))
                    else:
                        self.data_queue.put(None)
                        self.exception_queue.put(
                            RuntimeError(
                                "Key requested from host but no seed-key algorithm has been provided"
                            )
                        )

    def _parse_dm16(
        self, priority: int, pgn: int, sa: int, timestamp: int, data: bytearray
    ) -> None:
        """
        parse DM16 message received from device, used to parse data received from device on a read command
        :param int priority: priority of the message
        :param int pgn: parameter group number of the message
        :param int sa: source address of the message
        :param int timestamp: timestamp of the message
        :param bytearray data: data of the PDU
        """
        if pgn != j1939.ParameterGroupNumber.PGN.DM16 or sa != self._dest_address:
            return
        if data[0] == 0xFF:
            length = len(data) - 1
        else:
            length = min(data[0], 7)
        self.mem_data = data[1 : length + 1]
        self._ca.unsubscribe(self._parse_dm16)
        self._ca.subscribe(self._parse_dm15)
        self.state = QueryState.WAIT_FOR_OPER_COMPLETE

    def _values_to_bytes(self, values: list) -> bytearray:
        """
        convert values to bytes for sending to device
        :param list values: values to be converted to bytes
        """
        bytes = []
        for val in values:
            bytes.extend(val.to_bytes(self.object_byte_size, byteorder="little"))
        return bytes

    def _bytes_to_values(self, raw_bytes: bytearray) -> list:
        """
        convert bytes received from device to values
        :param bytearray raw_bytes: bytes received from device
        """
        values = []
        for i in range(0, len(raw_bytes), self.object_byte_size):
            values.append(
                int.from_bytes(
                    raw_bytes[i : i + self.object_byte_size],
                    byteorder="little",
                    signed=self.signed,
                )
            )
        return values

    def read(
        self,
        dest_address: int,
        direct: int,
        address: int,
        object_count: int,
        object_byte_size: int = 1,
        signed: bool = False,
        return_raw_bytes: bool = False,
        max_timeout: int = 1,
    ) -> list:
        """
        Send a read query to dest_address, requesting data at address
        :param int dest_address: destination address of the message
        :param int direct: direct address of the message
        :param int address: address of the message
        :param int object_count: number of objects to be read
        :param int object_byte_size: size of each object in bytes
        :param bool signed: whether the data is signed
        :param bool return_raw_bytes: whether to return raw bytes or values
        :param int max_timeout: max timeout for transaction
        """
        assert object_count > 0
        assert object_count <= 1784
        self._dest_address = dest_address
        self.direct = direct
        self.address = address
        self.object_count = object_count
        self.object_byte_size = object_byte_size
        self.signed = signed
        self.return_raw_bytes = return_raw_bytes
        self.command = Command.READ
        self.state = QueryState.WAIT_FOR_SEED
        self._ca.subscribe(self._parse_dm15)
        self._send_dm14(7)
        # wait for operation completed DM15 message
        raw_bytes = None
        try:
            raw_bytes = self.data_queue.get(block=True, timeout=max_timeout)
        except queue.Empty:
            if self.state is QueryState.WAIT_FOR_SEED:
                raise RuntimeError("No response from server")
            pass
        for _ in range(self.exception_queue.qsize()):
            raise self.exception_queue.get(block=False, timeout=max_timeout)
        if raw_bytes:
            if self.return_raw_bytes:
                return raw_bytes
            else:
                return self._bytes_to_values(raw_bytes)
        else:
            return []

    def write(
        self,
        dest_address: int,
        direct: int,
        address: int,
        values: list,
        object_byte_size: int = 1,
        max_timeout: int = 1,
    ) -> None:
        """
        Send a write query to dest_address, requesting to write values at address
        :param int dest_address: destination address of the message
        :param int direct: direct address of the message
        :param int address: address of the message
        :param list values: values to be written
        :param int object_byte_size: size of each object in bytes
        :param int max_timeout: max timeout for transaction
        """
        self._dest_address = dest_address
        self.direct = direct
        self.address = address
        self.object_byte_size = object_byte_size
        self.command = Command.WRITE
        self.bytes = self._values_to_bytes(values)
        self.object_count = len(values)
        assert self.object_count <= 1784
        self.state = QueryState.WAIT_FOR_SEED
        self._ca.subscribe(self._parse_dm15)
        self._send_dm14(7)
        # wait for operation completed DM15 message
        try:
            self.data_queue.get(block=True, timeout=max_timeout)
            for _ in range(self.exception_queue.qsize()):
                raise self.exception_queue.get(block=False, timeout=max_timeout)
        except queue.Empty:
            if self.state is QueryState.WAIT_FOR_SEED:
                raise RuntimeError("No response from server")
            pass  # expect empty queue for write

    def set_seed_key_algorithm(self, algorithm: callable) -> None:
        """
        set seed-key algorithm to be used for key generation
        :param callable algorithm: seed-key algorithm
        """
        self._seed_from_key = algorithm
