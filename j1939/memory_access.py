from enum import Enum
import queue
import sys
import time
import secrets
import j1939
import Dm14Query
import Dm14Response


class QueryState(Enum):
    IDLE = 1
    REQUEST_STARTED = 2
    WAIT_CALLBACKS = 3


class Command(Enum):
    ERASE = 0
    READ = 1
    WRITE = 2
    STATUS_REQUEST = 3
    OPERATION_COMPLETED = 4
    OPERATION_FAILED = 5
    BOOT_LOAD = 6
    EDCP_GENERATION = 7


class ResponseState(Enum):
    IDLE = 1
    WAIT_FOR_DM14 = 2
    WAIT_FOR_KEY = 3
    SEND_PROCEED = 4


class ReceiveState(Enum):
    IDLE = 1
    WAIT_FOR_KEY = 2
    WAIT_FOR_CONFIRMATION = 3


class Dm15Status(Enum):
    PROCEED = 0
    BUSY = 1
    OPERATION_COMPLETE = 4
    OPERATION_FAILED = 5


class MemoryAccess:
    def __init__(self, ca: j1939.ControllerApplication) -> None:
        """
        Makes an overarching Memory access class
        :param ca: Controller Application
        :param receive_addr: Address of the device expected to receive memory accesses from
        """
        self._ca = ca
        self.query = Dm14Query.DM14Query(ca)
        self.response = Dm14Response.DM14Response(ca)
        self._ca.subscribe(self._listen_for_dm14)
        self.state = QueryState.IDLE
        self._spatial_function = None
        self._seed_key_valid = None
        self._proceed_function = None

    def _listen_for_dm14(
        self, priority: int, pgn: int, sa: int, timestamp: int, data: bytearray
    ) -> None:
        """
        Listens for dm14 messages and passes them to the appropriate function
        :param priority: Priority of the message
        :param pgn: Parameter Group Number of the message
        :param sa: Source Address of the message
        :param timestamp: Timestamp of the message
        :param data: Data of the PDU
        """
        if self.state is QueryState.IDLE:
            self.state = QueryState.REQUEST_STARTED
            self.response._parse_dm14(priority, pgn, sa, timestamp, data)
        elif self.state is QueryState.REQUEST_STARTED:
            self.state = QueryState.WAIT_CALLBACKS
            self.query._parse_dm14(priority, pgn, sa, timestamp, data)
            self._ca.unsubscribe(self._listen_for_dm14)
            self._callbacks()

    def _callbacks(self) -> None:
        """
        Handles calling callbacks for the memory access class
        """
        if self._spatial_function is not None:
            self._spatial_function(
                self.response.access_level,
                self.response.sa,
                self.response.address,
                self.response.length,
                self.response.direct,
                self.response.command,
                self.response.object_count,
                self.response.data_queue,
            )
        if self._seed_key_valid is not None:
            self.valid = self._seed_key_valid(self.response.seed, self.response.key)
        if self._proceed_function is not None:
            self.proceed = self._proceed_function()

    def set_spatial_function(self, function: callable) -> None:
        """
        set spatial function to be used for handling queries
        :param callable function: spatial function
        """
        self._spatial_function = function

    def set_is_seed_key_valid_function(self, function: callable) -> None:
        """
        set is-seed-key-valid function to be used for key verification
        :param callable function: is-seed-key-valid function
        """
        self._seed_key_valid = function

    def set_proceed_function(self, function: callable) -> None:
        """
        set proceed function to be used for handling proceed messages
        :param callable function: proceed function
        """
        self._proceed_function = function

    def set_seed_key_algorithm(self, algorithm: callable) -> None:
        """
        set seed-key algorithm to be used for key generation
        :param callable algorithm: seed-key algorithm
        """
        self.query.set_seed_key_algorithm(algorithm)
        self.response.set_seed_key_algorithm(algorithm)
