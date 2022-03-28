from enum import Enum
import queue
import sys
import time

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


class ReceiveState(Enum):
    IDLE = 1
    WAIT_FOR_KEY = 2
    WAIT_FOR_CONFIRMATION = 3


class Dm15Status(Enum):
    PROCEED = 0
    BUSY = 1
    OPERATION_COMPLETE = 4
    OPERATION_FAILED = 5


class Dm14Query:
    def __init__(self, ca: j1939.ControllerApplication):
        """
        performs memory access queries using DM14-DM18 messaging.  Presently only read queries are supported

        :param obj ca: j1939 controller application
        """

        self._ca = ca
        self.state = QueryState.IDLE
        self._seed_from_key = None
        self.data_queue = queue.Queue()
        self.mem_data = None

    def _wait_for_data(self):
        assert self.state is QueryState.WAIT_FOR_SEED
        if self.command is Command.WRITE:
            self._send_dm16()
            self.state = QueryState.WAIT_FOR_OPER_COMPLETE
        else:
            self.state = QueryState.WAIT_FOR_DM16
            self._ca.unsubscribe(self._parse_dm15)
            self._ca.subscribe(self._parse_dm16)

    def _send_operation_complete(self):
        self.object_count = 1
        self.command = Command.OPERATION_COMPLETED
        self._send_dm14(0xFFFF)

    def _send_dm14(self, key_or_user_level):
        self._pgn = j1939.ParameterGroupNumber.PGN.DM14
        pointer = self.address.to_bytes(length=4, byteorder="little")
        data = []
        data.append(self.object_count)
        data.append(
            (self.direct << 4) + (self.command.value << 1) + 1
        )  # (SAE reserved = 1)
        for octet in pointer:
            data.append(octet)
        data.append(key_or_user_level & 0xFF)
        data.append(key_or_user_level >> 8)
        self._ca.send_pgn(
            0, (self._pgn >> 8) & 0xFF, self._dest_address & 0xFF, 6, data
        )

    def _send_dm16(self):
        self._pgn = j1939.ParameterGroupNumber.PGN.DM16
        data = []
        byte_count = len(self.bytes)
        data.append(0xFF if byte_count > 7 else byte_count)
        for i in range(byte_count):
            data.append(self.bytes[i])
        self._ca.send_pgn(
            0, (self._pgn >> 8) & 0xFF, self._dest_address & 0xFF, 6, data
        )

    def _parse_dm15(self, priority, pgn, sa, timestamp, data):
        if pgn != j1939.ParameterGroupNumber.PGN.DM15 or sa != self._dest_address:
            return
        seed = (data[7] << 8) + data[6]
        status = (data[1] >> 1) & 7
        if status is Dm15Status.BUSY.value or status is Dm15Status.OPERATION_FAILED:
            error = int.from_bytes(data[2:4], byteorder="little", signed=False)
            self.data_queue.put(None)
            if error == 0x1000:
                raise RuntimeError("Key authentication error")
            else:  # TODO parse error codes more granularly
                raise RuntimeError(f"Device {sa} busy")
        length = data[0]
        if seed == 0xFFFF and length == self.object_count:
            self._wait_for_data()
        else:
            if self.state is QueryState.WAIT_FOR_OPER_COMPLETE:
                assert status is Command.OPERATION_COMPLETED.value
                self._send_operation_complete()
                self.state = QueryState.IDLE
                self.data_queue.put(self.mem_data)
            else:
                assert self.state is QueryState.WAIT_FOR_SEED
                if self._seed_from_key is not None:
                    self._send_dm14(self._seed_from_key(seed))
                else:
                    self.data_queue.put(None)
                    raise RuntimeError(
                        "Key requested from host but no seed-key algorithm has been provided"
                    )

    def _parse_dm16(self, priority, pgn, sa, timestamp, data):
        if pgn != j1939.ParameterGroupNumber.PGN.DM16 or sa != self._dest_address:
            return
        length = min(data[0], len(data) - 1)
        # assert object_count == self.object_count
        self.mem_data = data[1 : length + 1]
        self._ca.unsubscribe(self._parse_dm16)
        self._ca.subscribe(self._parse_dm15)
        self.state = QueryState.WAIT_FOR_OPER_COMPLETE

    def _values_to_bytes(self, values):
        bytes = []
        for val in values:
            bytes.extend(val.to_bytes(self.object_byte_size, byteorder="little"))
        return bytes

    def _bytes_to_values(self, raw_bytes):
        values = []
        for i in range(len(raw_bytes) // self.object_byte_size):
            values.append(
                int.from_bytes(
                    raw_bytes[i : self.object_byte_size],
                    byteorder="little",
                    signed=self.signed,
                )
            )
        return values

    def read(
        self,
        dest_address,
        direct,
        address,
        object_count,
        object_byte_size=1,
        signed=False,
        return_raw_bytes=False,
    ):
        assert object_count > 0
        self._dest_address = dest_address
        self.direct = direct
        self.address = address
        self.object_count = object_count
        self.object_byte_size = object_byte_size
        self.signed = signed
        self.return_raw_bytes = return_raw_bytes
        self.command = Command.READ
        self._ca.subscribe(self._parse_dm15)
        self._send_dm14(7)
        self.state = QueryState.WAIT_FOR_SEED
        # wait for operation completed DM15 message
        raw_bytes = self.data_queue.get(block=True, timeout=1)
        if self.return_raw_bytes:
            return raw_bytes
        else:
            return self._bytes_to_values(raw_bytes)

    def write(self, dest_address, direct, address, values, object_byte_size=1):
        self._dest_address = dest_address
        self.direct = direct
        self.address = address
        self.object_byte_size = object_byte_size
        self.command = Command.WRITE
        self.bytes = self._values_to_bytes(values)
        self.object_count = len(values)
        self._ca.subscribe(self._parse_dm15)
        self._send_dm14(7)
        self.state = QueryState.WAIT_FOR_SEED
        # wait for operation completed DM15 message
        try:
            self.data_queue.get(block=True, timeout=1)
        except queue.Empty:
            pass  # expect empty queue for write

    def set_seed_key_algorithm(self, algorithm):
        self._seed_from_key = algorithm

    def set_seed_key_algorithm(self, algorithm):
        self._seed_from_key = algorithm
