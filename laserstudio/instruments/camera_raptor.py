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
