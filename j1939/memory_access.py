from enum import Enum
import queue
import sys
import time
import secrets
import j1939


class QueryState(Enum):
    IDLE = 1
    REQUEST_STARTED = 2
    WAIT_RESPONSE = 3


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
        self.query = j1939.Dm14Query(ca)
        self.response = j1939.DM14Response(ca)
        self._ca.subscribe(self._listen_for_dm14)
        self.state = QueryState.IDLE
        self.seed_securirty = False
        self._notify_query_received = None
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
        match self.state:
            case QueryState.IDLE:
                self.state = QueryState.REQUEST_STARTED
                self.response._parse_dm14(priority, pgn, sa, timestamp, data)
                if not self.seed_securirty:
                    self._ca.unsubscribe(self._listen_for_dm14)
                    if self._notify_query_received is not None:
                        self._notify_query_received()  # notify incoming request

            case QueryState.REQUEST_STARTED:
                self.state = QueryState.WAIT_RESPONSE
                self.response._parse_dm14(priority, pgn, sa, timestamp, data)
                self._ca.unsubscribe(self._listen_for_dm14)
                if self._notify_query_received is not None:
                    self._notify_query_received()  # notify incoming request

    def respond(
        self, proceed: bool, data: list = [], error: int = 0xFFFFFF, edcp: int = 0xFF
    ) -> list:
        """
        Responds with requested data and error code, if applicable, to a read request
        """
        self._ca.unsubscribe(self._listen_for_dm14)
        self.state = QueryState.IDLE
        return self.response.respond(proceed, data, error, edcp)

    def set_seed_generator(self, seed_generator: callable) -> None:
        """
        Sets seed generator function to use
        :param seed_generator: seed generator function
        """
        self.response.set_seed_generator(seed_generator)

    def set_seed_key_algorithm(self, algorithm: callable) -> None:
        """
        set seed-key algorithm to be used for key generation
        :param callable algorithm: seed-key algorithm
        """
        self.seed_securirty = True
        self.query.set_seed_key_algorithm(algorithm)
        self.response.set_seed_key_algorithm(algorithm)

    def set_notify(self, notify: callable) -> None:
        """
        set notify function to be used for notifying the user of memory accesses
        :param callable notify: notify function
        """
        self._notify_query_received = notify
