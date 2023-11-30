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
    J1939Error.NO_ERROR.value: "No error",
    J1939Error.UNKNOWN_ERROR.value: "Unknown error",
    J1939Error.BUSY.value: "Busy",
    J1939Error.BUSY_ERASE_REQUEST.value: "Busy: erase request",
    J1939Error.BUSY_READ_REQUEST.value: "Busy: read request",
    J1939Error.BUSY_WRITE_REQUEST.value: "Busy: write request",
    J1939Error.BUSY_STATUS_REQUEST.value: "Busy status request",
    J1939Error.BUSY_BOOT_LOAD_REQUEST.value: "Busy: boot load request",
    J1939Error.BUSY_EDCP_GENERATION_REQUEST.value: "Busy: EDCP generation request",
    J1939Error.BUSY_UNKNOW_REQUEST.value: "Busy: unknown request",
    J1939Error.EDC_PARAMETER_ERROR.value: "EDC parameter error",
    J1939Error.RAM_ERROR.value: "RAM error",
    J1939Error.FLASH_ERROR.value: "Flash error",
    J1939Error.PROM_ERROR.value: "PROM error",
    J1939Error.INTERNAL_ERROR.value: "Internal error",
    J1939Error.GENERAL_ADDRESSING_ERROR.value: "General addressing error",
    J1939Error.ADDRESS_NOT_ON_BOUNDARY.value: "Address: not on boundary",
    J1939Error.ADDRESS_INVALID_LENGTH.value: "Address: invalid length",
    J1939Error.ADDRESS_MEMORY_OVERFLOW.value: "Address: memory overflow",
    J1939Error.ADDRESS_DATA_ERASE_REQUIRED.value: "Address: data erase required",
    J1939Error.ADDRESS_PROGRAM_ERASE_REQUIRED.value: "Address: program erase required",
    J1939Error.ADDRESS_TX_ERASE_PROGRAM_REQUIRED.value: "Address: TX erase program required",
    J1939Error.ADDRESS_BOOT_LOAD_OUT_OF_RANGE.value: "Address: boot load out of range",
    J1939Error.ADDRESS_BOOT_LOAD_NOT_ON_BOUNDARY.value: "Address: boot load not on boundary",
    J1939Error.DATA_OUT_OF_RANGE.value: "Data out of range",
    J1939Error.DATA_NAME_UNEXPECTED.value: "Data name unexpected",
    J1939Error.SECURITY_GENERAL.value: "Security: general",
    J1939Error.SECURITY_INVALID_PASSWORD.value: "Security: invalid password",
    J1939Error.SECURITY_INVALID_LEVEL.value: "Security: invalid level",
    J1939Error.SECURITY_INVALID_KEY.value: "Security: invalid key",
    J1939Error.SECURITY_NOT_DIAGNOSTIC.value: "Security: not diagnostic",
    J1939Error.SECURITY_INCORRECT_MODE.value: "Security: incorrect mode",
    J1939Error.SECURITY_ENGINE_RUNNING.value: "Security: engine running",
    J1939Error.SECURITY_VEHICLE_MOVING.value: "Security: vehicle moving",
    J1939Error.ABORT_EXTERNAL.value: "Abort external",
    J1939Error.MAX_RETRY.value: "Max retry",
    J1939Error.NO_RESPONSE.value: "No response",
    J1939Error.INITILIZATION_TIMEOUT.value: "Initilization timeout",
    J1939Error.COMPLETION_TIMEOUT.value: "Completion timeout",
    J1939Error.NO_INDICATOR.value: "No indicator",
}