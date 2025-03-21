from pylmscontroller import LMSController, MotorState, ControlMode
from .shutter import ShutterInstrument
from .light import LightInstrument
from .list_serials import get_serial_device
from typing import cast


_shared_device: dict[str, LMSController] = {}


class LMSControllerInstrument(ShutterInstrument, LightInstrument):
    def __init__(self, config: dict):
        super(ShutterInstrument, self).__init__(config)
        super(LightInstrument, self).__init__(config)

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

        self.lms.motors_control_mode = ControlMode.SOFTWARE
        self.lms.led_control = ControlMode.SOFTWARE
        self.lms.apply()

    # Shutter operations
    @property
    def open(self):
        return super().open

    @open.setter
    def open(self, value: bool):
        super(LMSControllerInstrument, type(self)).open.fset(self, value)
        # k = super(LMSControllerInstrument)
        # super(ShutterInstrument, self).open = value
        state = MotorState.SLIDE_IN if value else MotorState.SLIDE_OUT
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
