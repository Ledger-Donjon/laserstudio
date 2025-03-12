from .camera_usb import CameraUSBInstrument
from .list_serials import (
    get_serial_device,
    DeviceSearchError,
    serial,
    ConnectionFailure,
    ProtocolError,
)
from serial.serialutil import SerialException
import logging
from typing import Optional, Literal, NamedTuple
from enum import Enum, IntFlag
import numpy
import math
from PyQt6.QtCore import pyqtSignal
from datetime import date


class RaptorCameraGainTrigger(IntFlag):
    """
    Bit 6 = 1 to enable Ext trig
    Bit 5 = 0 for –ve edge trig
    Bit 4 = 1 to enable High Gain Trigger mode 2
    Bit 2 = 0 for low gain, 1 for high gain
    Bit 1 = 0 for low gain, 1 for high gain
    Note: bits 2 and 1 should be set to the same value.
    Note: gain mode cannot be set if auto gain mode
    control is enabled (camera control register 1, bit 1)
    """

    EXT_TRIG = 1 << 6
    HIGH_GAIN_TRIGGER_MODE_2 = 1 << 4
    HIGH_GAIN = 0b11 << 1


class RaptorCameraControlReg0(IntFlag):
    """
    Bit 7 = 1 if horiz flip is enabled (default = 1)
    Bit 6 = 1 if video is inverted (default = 0)
    Bits 5..3 = reserved
    Bit 2 = 1 if FAN enabled ?(default = 0)
    Bit 1 = 1 if ALC is enabled (default = 0)
    Bit 0 = 1 if the TEC is enabled (default = 0)
    """

    HORIZ_FLIP = 1 << 7
    VIDEO_INVERTED = 1 << 6
    FAN_ENABLED = 1 << 2
    ALC_ENABLED = 1 << 1
    TEC_ENABLED = 1


class RaptorCameraControlReg1(IntFlag):
    """
    Bit 7..2 = unused (default = 0)
    YY bit 1 = 1 if AGMC is enabled (default = 1)
    Bit 0 = 1 if the fan is enabled (default = 0, note
    this only applies to the Owl 640 cooled variant)
    """

    AGMC_ENABLED = 1 << 1
    FAN_ENABLED = 1


class RaptorSystemStatus(IntFlag):
    """
    YY bit 6 = 1 if check sum mode enabled
    YY bit 4 = 1 if command ack enabled
    YY bit 2 = 1 if FPGA booted successfully
    YY bit 1 = 0 if FPGA is held in RESET
    YY bit 0 = 1 if comms is enabled to FPGA NVM
    """

    CHECK_SUM_MODE = 1 << 6
    COMMAND_ACK = 1 << 4
    FPGA_BOOTED = 1 << 2
    FPGA_RESET = 1 << 1
    COMMS_ENABLED = 1


class RaptorManufacturersData(NamedTuple):
    serial_number: int
    build_date: date
    buildcode: str
    adc_cal_0_deg: int
    adc_cal_40_deg: int
    dac_cal_0_deg: int
    dac_cal_40_deg: int

    @staticmethod
    def from_bytes(data: bytes) -> "RaptorManufacturersData":
        """
        Get 18 bytes from cameras NVM.
        For 2 byte values 1st byte returned is the LSB.
        Starting at address 0x000002
        2 bytes Serial number
        3 bytes Build Date (DD/MM/YY)
        5 bytes Build code (5 ASCII chars)
        2 bytes ADC cal 0°C point
        2 bytes ADC cal+40°C point
        2 bytes DAC cal 0°C point
        2 bytes DAC cal+40°C point
        """
        serial_number = int.from_bytes(data[0:2], "little")
        build_date = date(int(data[2]) + 2000, int(data[3]), int(data[4]))  # DD/MM/YY
        buildcode = data[5:10].decode("ascii")
        adc_cal_0_deg = int.from_bytes(data[10:12], "little")
        adc_cal_40_deg = int.from_bytes(data[12:14], "little")
        dac_cal_0_deg = int.from_bytes(data[14:16], "little")
        dac_cal_40_deg = int.from_bytes(data[16:18], "little")
        return RaptorManufacturersData(
            serial_number,
            build_date,
            buildcode,
            adc_cal_0_deg,
            adc_cal_40_deg,
            dac_cal_0_deg,
            dac_cal_40_deg,
        )


class RaptorErrorCode(bytes, Enum):
    ETX = b"\x50"  # Command acknowledge - Command processed successfully.
    ETX_SER_TIMEOUT = b"\x51"  # Partial command packet received, camera timed out waiting for end of packet. - Command not processed
    ETX_CK_SUM_ERR = b"\x52"  # Check sum transmitted by host did not match that calculated for the packet. - Command not processed
    ETX_I2C_ERR = b"\x53"  # An I2C command has been received from the Host but failed internally in the camera.
    ETX_UNKNOWN_CMD = (
        b"\x54"  # Data was detected on serial line, command not recognized.
    )
    ETX_DONE_LOW = b"\x55"  # Host Command to access the camera NVM successfully received by camera.

    def __str__(self) -> str:
        if self == RaptorErrorCode.ETX:
            return "Command acknowledge - Command processed successfully."
        elif self == RaptorErrorCode.ETX_SER_TIMEOUT:
            return "Partial command packet received, camera timed out waiting for end of packet. - Command not processed"
        elif self == RaptorErrorCode.ETX_CK_SUM_ERR:
            return "Check sum transmitted by host did not match that calculated for the packet. - Command not processed"
        elif self == RaptorErrorCode.ETX_I2C_ERR:
            return "An I2C command has been received from the Host but failed internally in the camera."
        elif self == RaptorErrorCode.ETX_UNKNOWN_CMD:
            return "Data was detected on serial line, command not recognized."
        elif self == RaptorErrorCode.ETX_DONE_LOW:
            return (
                "Host Command to access the camera NVM successfully received by camera."
            )
        else:
            return super().__str__()


class RaptorCommand(bytes, Enum):
    GET_SYSTEM_STATUS = b"\x49"
    SET_ADDRESS = b"\x53\xe0"
    GET_VALUE = b"\x53\xe1"
    MICRO_RESET = b"\x55"
    GET_MICRO_VERSION = b"\x56"
    GET_MANUFACTURERS_DATA = b"\x53\xae\x05\x01\x00\x00\x02\x00"
    GET_MANUFACTURERS_DATA_VALUE = b"\x53\xaf"


class CameraRaptorInstrument(CameraUSBInstrument):
    """Class to implement the Raptor cameras"""

    def read_raptor_register(self, address: int) -> int:
        """
        Reads a register from the camera.

        :param address: The address of the register to read.
        :return: The value of the register.
        """
        self.serial.write(b"\x53\xe0\x01" + address.to_bytes(1, "big") + b"\x50")
        self.serial.write(b"\x53\xe1\x01\x50")
        response = self.serial.read(3)
        if len(response) == 0:
            raise ProtocolError(f"No response while reading register {address}")
        if len(response) == 1 or response[-1] != 0x50:
            raise ProtocolError(f"Error: {response}", -response[-1])

        return response[-2]

    def get_micro_version(self) -> tuple[int, int]:
        """
        Gets the micro version of the camera.

        :return: The micro version of the camera.
        """
        self.serial.write(b"\x56\x50")
        response = self.serial.read(4)
        return response[2], response[3]

    def get_serial_number(self) -> str:
        """
        Gets the serial number of the camera.

        :return: The serial number of the camera.
        """

    def __init__(self, config: dict):
        super().__init__(config)

        dev = config.get("dev")
        if dev is None:
            logging.getLogger("laserstudio").error(
                "In configuration file, 'dev' is mandatory for type 'Raptor'"
            )
            raise

        try:
            dev = get_serial_device(dev)
        except DeviceSearchError as e:
            logging.getLogger("laserstudio").error(
                f"Raptor camera is enabled but is not found: {str(e)}... Skipping."
            )
            raise
        try:
            self.serial = serial.Serial(dev, 115200, timeout=1)
        except SerialException as e:
            raise ConnectionFailure() from e
