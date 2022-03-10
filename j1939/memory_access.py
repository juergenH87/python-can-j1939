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
        self.length = 1
        self.command = Command.OPERATION_COMPLETED
        self._send_dm14(0xFFFF)

    def _send_dm14(self, key_or_user_level):
        self._pgn = j1939.ParameterGroupNumber.PGN.DM14
        pointer = self.address.to_bytes(length=4, byteorder="little")
        data = [0xFF] * 8
        data[0] = self.length
        data[1] = (
            (self.direct << 4) + (self.command.value << 1) + 1
        )  # (SAE reserved = 1)
        i = 2
        for octet in pointer:
            data[i] = octet
            i = i + 1
        data[6] = key_or_user_level & 0xFF
        data[7] = key_or_user_level >> 8
        self._ca.send_pgn(
            0, (self._pgn >> 8) & 0xFF, self._dest_address & 0xFF, 6, data
        )

    def _send_dm16(self):
        self._pgn = j1939.ParameterGroupNumber.PGN.DM16
        data = [0xFF] * 8
        byte_count = len(self.bytes)
        data[0] = 0xFF if byte_count > 7 else byte_count
        for i in range(byte_count):
            data[i + 1] = self.bytes[i]
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
        if seed == 0xFFFF and length == self.length:
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
        # assert length == self.length
        self.mem_data = data[1 : length + 1]
        self._ca.unsubscribe(self._parse_dm16)
        self._ca.subscribe(self._parse_dm15)
        self.state = QueryState.WAIT_FOR_OPER_COMPLETE

    def _values_to_bytes(self, values):
        bytes = []
        for val in values:
            bits = (val.bit_length() + 7) // 8
            bytes.extend(val.to_bytes(bits, byteorder="little"))
        return bytes


    def read(self, dest_address, direct, address, length):
        assert length > 0
        self._dest_address = dest_address
        self.direct = direct
        self.address = address
        self.length = length
        self.command = Command.READ
        self._ca.subscribe(self._parse_dm15)
        self._send_dm14(7)
        self.state = QueryState.WAIT_FOR_SEED
        # wait for operation completed DM15 message
        return self.data_queue.get(block=True, timeout=1)

    def write(self, dest_address, direct, address, values):
        self._dest_address = dest_address
        self.direct = direct
        self.address = address
        self.command = Command.WRITE
        self.bytes = self._values_to_bytes(values)
        self.length = len(values)
        self._ca.subscribe(self._parse_dm15)
        self._send_dm14(7)
        self.state = QueryState.WAIT_FOR_SEED
        # wait for operation completed DM15 message
        try:
            self.data_queue.get(block=True, timeout=1)
        except queue.Empty:
            pass #expect empty queue for write 


    def set_seed_key_algorithm(self, algorithm):
        self._seed_from_key = algorithm


    def set_seed_key_algorithm(self, algorithm):
        self._seed_from_key = algorithm
