from __future__ import annotations

import logging
from pylmscontroller import LMSController, MotorState, ControlMode
from typing import cast
from .shutter import ShutterInstrument
from .light import LightInstrument
from .list_serials import get_serial_device
from ..utils.yaml_types import Config


_shared_device: dict[str, LMSController] = {}


class LMSControllerInstrument(ShutterInstrument, LightInstrument):
    def __init__(self, config: Config):
        ShutterInstrument.__init__(self, config)
        LightInstrument.__init__(self, config)

        dev = config.get("dev")
        if dev == "":
            dev = None
        if isinstance(dev, str) or isinstance(dev, dict):
            dev = get_serial_device(dev)

        assert type(dev) is str, (
            f"'dev' must be a string, and is {type(dev) if dev is not None else None}"
        )
        self.lms = _shared_device.get(dev, LMSController(dev))
        self.motor = cast(int, config.get("motor", 1))
        assert self.motor in (1, 2, 3), "Motor index must be 1, 2, or 3"

        self.open_is_slidein = cast(bool, config.get("open_is_slidein", True))

        self.lms.motors_control_mode = ControlMode.SOFTWARE
        self.lms.led_control = ControlMode.SOFTWARE
        self.lms.apply()

    # Shutter operations
    @property
    def open(self) -> bool:
        """
        Whether the shutter is open (eg camera can acquire images, light source is on...).
        """
        if self.motor == 1:
            state = self.lms.measured_motor_1_position
        elif self.motor == 2:
            state = self.lms.measured_motor_2_position
        elif self.motor == 3:
            state = self.lms.measured_motor_3_position
        else:
            raise ValueError(f"Invalid motor index: {self.motor}")

        # Consider the open_is_slidein configuration
        return (
            state == MotorState.SLIDE_IN
            if self.open_is_slidein
            else state == MotorState.SLIDE_OUT
        )

    @open.setter
    def open(self, value: bool):
        ShutterInstrument.open.__set__(self, value)
        # open == true  & open_is_slidein == true  => open^open_is_slidein == false => SLIDE_IN
        # open == false & open_is_slidein == true  => open^open_is_slidein == true  => SLIDE_OUT
        # open == true  & open_is_slidein == false => open^open_is_slidein == true  => SLIDE_OUT
        # open == false & open_is_slidein == false => open^open_is_slidein == false => SLIDE_IN
        state = (
            MotorState.SLIDE_OUT
            if (value ^ self.open_is_slidein)
            else MotorState.SLIDE_IN
        )
        if self.motor == 1:
            self.lms.motor_1_position = state
        elif self.motor == 2:
            self.lms.motor_2_position = state
        elif self.motor == 3:
            self.lms.motor_3_position = state
        self.lms.apply()

    # Light operations
    @property
    def light(self):
        """
        Whether the light is on.
        """
        return self.lms.led_activation

    @light.setter
    def light(self, value: bool):
        """
        Set the light to on or off.
        """
        self.lms.led_activation = value
        self.lms.apply()

    @property
    def intensity(self):
        """
        The intensity of the light in range [0.0, 1.0].
        """
        return self.lms.led_current / self.lms.MAX_IR_LED_CURRENT_MA

    @intensity.setter
    def intensity(self, value: float):
        """
        Set the intensity of the light in range [0.0, 1.0].
        """
        logging.getLogger("laserstudio").debug(f"Setting light intensity to {value}")
        value_float = float(int(value * self.lms.MAX_IR_LED_CURRENT_MA))
        logging.getLogger("laserstudio").debug(f"Applying: {value_float} to the device")
        self.lms.led_current = value_float
        self.lms.apply()

    def __del__(self):
        self.lms.led_control = ControlMode.MANUAL
        self.lms.motors_control_mode = ControlMode.MANUAL
        self.lms.apply()

    @property
    def settings(self) -> Config:
        """Export settings to a dict for yaml serialization."""
        settings = super().settings
        return settings

    @settings.setter
    def settings(self, data: Config):
        """Import and apply settings."""
        # Call the parent class settings setter
        if "intensity" in data and isinstance(data["intensity"], float):
            self.intensity = data["intensity"]
            self.parameter_changed.emit("intensity", data["intensity"])
        if "light" in data and isinstance(data["light"], bool):
            self.light = data["light"]
            self.parameter_changed.emit("light", data["light"])
        if "open" in data and isinstance(data["open"], bool):
            self.open = data["open"]
            self.parameter_changed.emit("open", data["open"])
