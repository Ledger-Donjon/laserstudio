from .camera_usb import CameraUSBInstrument
from .list_serials import (
    get_serial_device,
    DeviceSearchError,
    serial,
    ConnectionFailure,
)
from serial.serialutil import SerialException
import logging
from typing import Optional, Literal, NamedTuple, cast
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

        self.width = self.width // 2
        self.width_um = self.width_um // 2

        self.last_frame_number = 0

        self.manufacturers_data = None

        # Objective on this camera is 10x by default
        objective = cast(float, config.get("objective", 10.0))
        self.select_objective(objective)

    def query_command(
        self,
        command: RaptorCommand,
        data: bytes = b"",
        expected_bytes: int = 0,
        checksum=False,
    ) -> bytes:
        """
        The check sum byte should be the result of the Exclusive OR of all bytes in the Host command packet including the ETX byte.
        """
        whole_command = command.value + data + RaptorErrorCode.ETX.value
        if checksum:
            checksum = 0
            for byte in whole_command:
                checksum ^= byte
            whole_command += checksum.to_bytes(1, "big")

        # print(f"RAPTOR > {whole_command.hex()}")
        self.serial.write(whole_command)

        expected_bytes += 1  # Add ETX
        ret = bytes()
        while len(ret) < expected_bytes:
            # print(f"READing {expected_bytes - len(ret)} bytes")
            ret += self.serial.read(expected_bytes - len(ret))
            # print(f"RAPTOR < {ret.hex()}")
        return ret[:-1]

    def get_value_at_address(self, address: int, expected_bytes: int) -> bytes:
        return self.query_command(
            RaptorCommand.GET_VALUE, expected_bytes.to_bytes(1, "big"), expected_bytes
        )

    def write_raptor_register(self, address: int, value: int):
        """
        Writes a register to the camera.

        :param address: The address of the register to write.
        :param value: The value to write to the register (1 byte).
        """
        self.query_command(
            RaptorCommand.SET_ADDRESS,
            b"\x02" + address.to_bytes(1, "big") + value.to_bytes(1, "big"),
        )

    def read_raptor_register(self, address: int, expected_bytes: int = 1) -> int:
        """
        Reads a register from the camera.

        :param address: The address of the register to read.
        :return: The value of the register.
        """
        self.query_command(
            RaptorCommand.SET_ADDRESS, b"\x01" + address.to_bytes(1, "big")
        )
        value = self.get_value_at_address(address, expected_bytes)
        return int.from_bytes(value, "big")

    def get_micro_version(self) -> tuple[int, int]:
        """
        Gets the micro version of the camera.

        :return: The micro version of the camera.
        """
        response = self.query_command(RaptorCommand.GET_MICRO_VERSION, b"", 2)
        return response[0], response[1]

    def get_manufacturers_data(self) -> RaptorManufacturersData:
        """
        Gets the serial number of the camera.

        :return: The serial number of the camera.
        """
        self.query_command(RaptorCommand.GET_MANUFACTURERS_DATA)
        self.manufacturers_data = RaptorManufacturersData.from_bytes(
            self.query_command(RaptorCommand.GET_MANUFACTURERS_DATA_VALUE, b"\x12", 18)
        )
        return self.manufacturers_data

    def get_system_status(self) -> RaptorSystemStatus:
        status = self.query_command(RaptorCommand.GET_SYSTEM_STATUS, b"", 1)[0]
        return RaptorSystemStatus(status)

    def get_control_reg_0(self) -> RaptorCameraControlReg0:
        return RaptorCameraControlReg0(self.read_raptor_register(0))

    def get_control_reg_1(self) -> RaptorCameraControlReg1:
        return RaptorCameraControlReg1(self.read_raptor_register(1))

    def get_exposure_time(self) -> float:
        """
        Read address 0xEE (MSB), return 1 byte
        Read address 0xEF (MIDU), return 1 byte
        Read address 0xF0 (MIDL), return 1 byte
        Read address F1 (LSB), return 1 byte
        30 bit value, 4 bytes where:
        1 count = 1*40MHz period = 25nsecs
        2 Upper bits of 0xEE are don’t care’s.
        Min Exposure = 500nsec = 20counts
        """
        return (
            self.read_raptor_register(0xEE) << 24
            | self.read_raptor_register(0xEF) << 16
            | self.read_raptor_register(0xF0) << 8
            | self.read_raptor_register(0xF1)
        ) * 25e-9

    def get_exposure_time_ms(self) -> float:
        return self.get_exposure_time() * 1e3

    def set_exposure_time(self, value: float):
        """
        30 bit value, 4 separate commands,
        1 count = 1*40MHz period = 25nsecs
        Y1 = xxMMMMMM bits of 4 byte word
        Y4 = LLLLLLLL bits of 4 byte word
        Exposure updated on LSB write
        Min Exposure = 500nsec = 20counts
        Max Exposure = (2^30)*25ns ≈ 26.8secs"""
        counts = int(value / 25e-9)
        self.write_raptor_register(0xEE, (counts >> 24) & 0x3F)
        self.write_raptor_register(0xEF, (counts >> 16) & 0xFF)
        self.write_raptor_register(0xF0, (counts >> 8) & 0xFF)
        self.write_raptor_register(0xF1, counts & 0xFF)

    def set_exposure_time_ms(self, value: float):
        self.set_exposure_time(value * 1e-3)

    def get_digital_gain(self) -> float:
        """
        2 bytes returned MM,LL
        16bit value = gain*256
        Reg. C6 bits 7..0 = gain bits 15..8
        Reg. C7 bits 7..0 = level bits 7..0
        """
        v = self.read_raptor_register(0xC6) + self.read_raptor_register(0xC7) / 256.0
        return v

    def set_digital_gain(self, gain: float):
        """
        16bit value = gain*256
        MM bits 7..0 = gain bits 15..8
        LL bits 7..0 = level bits 7..0
        Data updated on write to LSBs
        Note: ALC must be disabled."
        """
        gain = int(gain * 256)
        self.write_raptor_register(0xC6, gain >> 8)
        self.write_raptor_register(0xC7, gain & 0xFF)

    def get_digital_gain_db(self) -> float:
        return 20 * math.log10(self.get_digital_gain())

    def set_digital_gain_db(self, value: float):
        self.set_digital_gain(10 ** (value / 20))

    def get_alc_enabled(self) -> bool:
        return bool(self.get_control_reg_0() & RaptorCameraControlReg0.ALC_ENABLED)

    def set_alc_enabled(self, value: bool):
        v = self.get_control_reg_0()
        if value:
            v |= RaptorCameraControlReg0.ALC_ENABLED
        else:
            v &= ~RaptorCameraControlReg0.ALC_ENABLED
        self.write_raptor_register(0, v)

    def get_tec_enabled(self) -> bool:
        return bool(self.get_control_reg_0() & RaptorCameraControlReg0.TEC_ENABLED)

    def set_tec_enabled(self, value: bool):
        v = self.get_control_reg_0()
        if value:
            v |= RaptorCameraControlReg0.TEC_ENABLED
        else:
            v &= ~RaptorCameraControlReg0.TEC_ENABLED
        self.write_raptor_register(0, v)

    def get_fan_enabled(self) -> bool:
        return bool(self.get_control_reg_0() & RaptorCameraControlReg0.FAN_ENABLED)

    def set_fan_enabled(self, value: bool):
        v = self.get_control_reg_0()
        if value:
            v |= RaptorCameraControlReg0.FAN_ENABLED
        else:
            v &= ~RaptorCameraControlReg0.FAN_ENABLED
        self.write_raptor_register(0, v)

    def get_agmc_enabled(self) -> bool:
        return bool(self.get_control_reg_1() & RaptorCameraControlReg1.AGMC_ENABLED)

    def set_agmc_enabled(self, value: bool):
        v = self.get_control_reg_1()
        if value:
            v |= RaptorCameraControlReg1.AGMC_ENABLED
        else:
            v &= ~RaptorCameraControlReg1.AGMC_ENABLED
        self.write_raptor_register(1, v)

    def get_fan2_enabled(self) -> bool:
        return bool(self.get_control_reg_1() & RaptorCameraControlReg1.FAN_ENABLED)

    def set_fan2_enabled(self, value: bool):
        v = self.get_control_reg_1()
        if value:
            v |= RaptorCameraControlReg1.FAN_ENABLED
        else:
            v &= ~RaptorCameraControlReg1.FAN_ENABLED
        self.write_raptor_register(1, v)

    def get_gain_trigger_mode(self) -> RaptorCameraGainTrigger:
        return RaptorCameraGainTrigger(self.read_raptor_register(0xF2))

    def set_gain_trigger_mode(self, value: RaptorCameraGainTrigger):
        self.write_raptor_register(0xF2, value)

    def get_high_gain_enabled(self) -> bool:
        return bool(self.get_gain_trigger_mode() & RaptorCameraGainTrigger.HIGH_GAIN)

    def set_high_gain_enabled(self, value: bool):
        v = self.get_gain_trigger_mode()
        if value:
            v |= RaptorCameraGainTrigger.HIGH_GAIN
        else:
            v &= ~RaptorCameraGainTrigger.HIGH_GAIN

        self.set_gain_trigger_mode(v)

    temperature_changed = pyqtSignal(float)

    def get_tec_temperature_setpoint(self) -> float:
        """
        12 bit DAC value, LSB = LL byte, Lower nibble of
        MM = MSBs
        Reg 0xFB, bits 3..0 = set point bits 11..8
        Reg 0xFA, bits 7..0 = set point bits 7..0
        12 bit value to be converted to temperature from
        DAC calibration values (see " Get manufacturers
        Data")
        """
        dac_count = self.read_raptor_register(0xFB) * 256 + self.read_raptor_register(
            0xFA
        )
        manufacturers_data = self.manufacturers_data
        if manufacturers_data is None:
            manufacturers_data = self.get_manufacturers_data()
        temperature = (
            (dac_count - manufacturers_data.dac_cal_0_deg)
            * (40 - 0)
            / (manufacturers_data.dac_cal_40_deg - manufacturers_data.dac_cal_0_deg)
        )
        return temperature

    def set_tec_temperature_setpoint(self, value: float):
        manufacturers_data = self.manufacturers_data
        if manufacturers_data is None:
            manufacturers_data = self.get_manufacturers_data()

        dac_count = int(
            (value - 0)
            * (manufacturers_data.dac_cal_40_deg - manufacturers_data.dac_cal_0_deg)
            / (40 - 0)
            + manufacturers_data.dac_cal_0_deg
        )
        self.write_raptor_register(0xFB, (dac_count >> 8) & 0x0F)
        self.write_raptor_register(0xFA, dac_count & 0xFF)

    def get_sensor_temperature(self) -> float:
        """
        Reg 6E, bits 3..0 = temp bits 11..8
        Reg 6F, bits 7..0 = temp bits 7..0
        12 bit value to be converted to temperature from
        ADC calibration values (see "Get manufacturers Data")
        """
        adc_count = self.read_raptor_register(0x6E) * 256 + self.read_raptor_register(
            0x6F
        )
        manufacturers_data = self.manufacturers_data
        if manufacturers_data is None:
            manufacturers_data = self.get_manufacturers_data()
        temperature = (
            (adc_count - manufacturers_data.adc_cal_0_deg)
            * (40 - 0)
            / (manufacturers_data.adc_cal_40_deg - manufacturers_data.adc_cal_0_deg)
        )

        self.temperature_changed.emit(temperature)
        return temperature

    def capture_image(self):
        ret, frame = self.vc.read()
        if not ret or frame is None:
            return None
        assert type(frame) is numpy.ndarray
        # Each value is repeated three times...
        frame = frame[:, :, :1].copy()
        # Flatten the array
        frame = numpy.reshape(frame, (-1,))
        # Frame number is present in the data
        number = frame[0:8]
        self.last_frame_number = number.view(numpy.uint32)[0]
        # Remove the 8 first bytes (containing the frame number)
        frame = frame[8:]
        # Interpret as 16 bits array
        frame = frame.view(numpy.uint16).copy()
        # Add 0s to the end to compensate the values that were removed for frame number
        frame = numpy.resize(frame, self.width * self.height)
        return frame
    
    def construct_display_image(self, pos, neg = None):
        # As we accumulated 16-bits images, we have to reduce it to 8-bits for display
        return super().construct_display_image(pos / 64.0, None if neg is None else neg / 64.0)
