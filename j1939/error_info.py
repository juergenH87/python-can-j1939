from enum import Enum

class J1939Error(Enum):
    """
    Enum of general errors based off of SAE Mobilus guidelines
    """
    NO_ERROR = 0x0
    UNKNOWN_ERROR = 0x1
    BUSY = 0x2
    BUSY_ERASE_REQUEST = 0x10
    BUSY_READ_REQUEST = 0x11
    BUSY_WRITE_REQUEST = 0x12
    BUSY_STATUS_REQUEST = 0x13
    BUSY_BOOT_LOAD_REQUEST = 0x16
    BUSY_EDCP_GENERATION_REQUEST = 0x17
    BUSY_UNKNOW_REQUEST = 0x1F
    EDC_PARAMETER_ERROR = 0x20
    RAM_ERROR = 0x21
    FLASH_ERROR = 0x22
    PROM_ERROR = 0x23
    INTERNAL_ERROR = 0x24
    GENERAL_ADDRESSING_ERROR = 0x100
    ADDRESS_NOT_ON_BOUNDARY = 0x101
    ADDRESS_INVALID_LENGTH = 0x102
    ADDRESS_MEMORY_OVERFLOW = 0x103
    ADDRESS_DATA_ERASE_REQUIRED = 0x104
    ADDRESS_PROGRAM_ERASE_REQUIRED = 0x105
    ADDRESS_TX_ERASE_PROGRAM_REQUIRED = 0x106
    ADDRESS_BOOT_LOAD_OUT_OF_RANGE = 0x107
    ADDRESS_BOOT_LOAD_NOT_ON_BOUNDARY = 0x108
    DATA_OUT_OF_RANGE = 0x109
    DATA_NAME_UNEXPECTED = 0x10A
    SECURITY_GENERAL = 0x1000
    SECURITY_INVALID_PASSWORD = 0x1001
    SECURITY_INVALID_LEVEL = 0x1002
    SECURITY_INVALID_KEY = 0x1003
    SECURITY_NOT_DIAGNOSTIC = 0x1004
    SECURITY_INCORRECT_MODE = 0x1005
    SECURITY_ENGINE_RUNNING = 0x1006
    SECURITY_VEHICLE_MOVING = 0x1007
    ABORT_EXTERNAL = 0x10000
    MAX_RETRY = 0x10001
    NO_RESPONSE = 0x10002
    INITILIZATION_TIMEOUT = 0x10003
    COMPLETION_TIMEOUT = 0x10004
    NO_INDICATOR = 0xFFFFFF


"""
Dictionary of error codes and their corresponding error message
"""
ErrorInfo = {
    J1939Error.NO_ERROR: "No error",
    J1939Error.UNKNOWN_ERROR: "Unknown error",
    J1939Error.BUSY: "Busy",
    J1939Error.BUSY_ERASE_REQUEST: "Busy: erase request",
    J1939Error.BUSY_READ_REQUEST: "Busy: read request",
    J1939Error.BUSY_WRITE_REQUEST: "Busy: write request",
    J1939Error.BUSY_STATUS_REQUEST: "Busy status request",
    J1939Error.BUSY_BOOT_LOAD_REQUEST: "Busy: boot load request",
    J1939Error.BUSY_EDCP_GENERATION_REQUEST: "Busy: EDCP generation request",
    J1939Error.BUSY_UNKNOW_REQUEST: "Busy: unknown request",
    J1939Error.EDC_PARAMETER_ERROR: "EDC parameter error",
    J1939Error.RAM_ERROR: "RAM error",
    J1939Error.FLASH_ERROR: "Flash error",
    J1939Error.PROM_ERROR: "PROM error",
    J1939Error.INTERNAL_ERROR: "Internal error",
    J1939Error.GENERAL_ADDRESSING_ERROR: "General addressing error",
    J1939Error.ADDRESS_NOT_ON_BOUNDARY: "Address: not on boundary",
    J1939Error.ADDRESS_INVALID_LENGTH: "Address: invalid length",
    J1939Error.ADDRESS_MEMORY_OVERFLOW: "Address: memory overflow",
    J1939Error.ADDRESS_DATA_ERASE_REQUIRED: "Address: data erase required",
    J1939Error.ADDRESS_PROGRAM_ERASE_REQUIRED: "Address: program erase required",
    J1939Error.ADDRESS_TX_ERASE_PROGRAM_REQUIRED: "Address: TX erase program required",
    J1939Error.ADDRESS_BOOT_LOAD_OUT_OF_RANGE: "Address: boot load out of range",
    J1939Error.ADDRESS_BOOT_LOAD_NOT_ON_BOUNDARY: "Address: boot load not on boundary",
    J1939Error.DATA_OUT_OF_RANGE: "Data out of range",
    J1939Error.DATA_NAME_UNEXPECTED: "Data name unexpected",
    J1939Error.SECURITY_GENERAL: "Security: general",
    J1939Error.SECURITY_INVALID_PASSWORD: "Security: invalid password",
    J1939Error.SECURITY_INVALID_LEVEL: "Security: invalid level",
    J1939Error.SECURITY_INVALID_KEY: "Security: invalid key",
    J1939Error.SECURITY_NOT_DIAGNOSTIC: "Security: not diagnostic",
    J1939Error.SECURITY_INCORRECT_MODE: "Security: incorrect mode",
    J1939Error.SECURITY_ENGINE_RUNNING: "Security: engine running",
    J1939Error.SECURITY_VEHICLE_MOVING: "Security: vehicle moving",
    J1939Error.ABORT_EXTERNAL: "Abort external",
    J1939Error.MAX_RETRY: "Max retry",
    J1939Error.NO_RESPONSE: "No response",
    J1939Error.INITILIZATION_TIMEOUT: "Initilization timeout",
    J1939Error.COMPLETION_TIMEOUT: "Completion timeout",
    J1939Error.NO_INDICATOR: "No indicator",
}