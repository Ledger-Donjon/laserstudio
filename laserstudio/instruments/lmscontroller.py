from pylmscontroller import LMSController, MotorState, ControlMode
from .shutter import ShutterInstrument
from .light import LightInstrument
from .list_serials import get_serial_device
from typing import cast


_shared_device: dict[str, LMSController] = {}


class LMSControllerInstrument(ShutterInstrument, LightInstrument):
    def __init__(self, config: dict):
        ShutterInstrument.__init__(self, config)
        LightInstrument.__init__(self, config)

        dev = config.get("dev")
        if dev == "":
            dev = None
        if dev is not None:
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
    def open(self):
        return ShutterInstrument.open.__get__(self)

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
        return self.lms.led_activation

    @light.setter
    def light(self, value: bool):
        self.lms.led_activation = value
        self.lms.apply()

    @property
    def intensity(self):
        return self.lms.led_current / self.lms.MAX_IR_LED_CURRENT

    @intensity.setter
    def intensity(self, value: float):
        self.lms.led_current = value * self.lms.MAX_IR_LED_CURRENT
        self.lms.apply()

    def __del__(self):
        self.lms.led_control = ControlMode.MANUAL
        self.lms.motors_control_mode = ControlMode.MANUAL
        self.lms.apply()

    @property
    def settings(self) -> dict:
        """Export settings to a dict for yaml serialization."""
        settings = super().settings
        return settings

    @settings.setter
    def settings(self, data: dict):
        """Import and apply settings."""
        # Call the parent class settings setter
        if "intensity" in data:
            self.intensity = data["intensity"]
            self.parameter_changed.emit("intensity", data["intensity"])
        if "light" in data:
            self.light = data["light"]
            self.parameter_changed.emit("light", data["light"])
        if "open" in data:
            self.open = data["open"]
            self.parameter_changed.emit("open", data["open"])
