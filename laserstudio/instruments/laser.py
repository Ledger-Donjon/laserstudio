from random import uniform
from PyQt6.QtCore import QVariant
import logging
from .probe import ProbeInstrument
from .shutter import ShutterInstrument
from .lmscontroller import LMSControllerInstrument
from ..utils.yaml_types import Config


class LaserInstrument(ProbeInstrument):
    def __init__(self, config: Config):
        super().__init__(config=config)
        # Sweep parameters, in order to change the current_percentage
        # regularly, within a random value from sweep_min to sweep_max,
        # each sweep_freq applications
        self.sweep_max = 100.0
        self.sweep_min = 0.0
        self.sweep_freq = 100
        self._sweep_iteration = 0

        # Shutter
        self.shutter: ShutterInstrument | None = None
        shutter = config.get("shutter")
        if isinstance(shutter, dict) and shutter.get("enable", True):
            try:
                device_type = shutter.get("type")
                if device_type == "LMSController":
                    self.shutter = LMSControllerInstrument(shutter)
                else:
                    logging.getLogger("laserstudio").error(
                        f"Unknown Shutter type {device_type}. Skipping device."
                    )
            except Exception as e:
                logging.getLogger("laserstudio").warning(
                    f"Shutter is enabled but device could not be created: {str(e)}... Skipping."
                )

    @property
    def on_off(self) -> bool: ...

    @on_off.setter
    def on_off(self, value: bool):
        self.parameter_changed.emit("on_off", QVariant(value))

    @property
    def current_percentage(self) -> float: ...

    @current_percentage.setter
    def current_percentage(self, value: float):
        self.parameter_changed.emit("current_percentage", QVariant(value))

    @property
    def offset_current(self) -> float: ...

    @offset_current.setter
    def offset_current(self, value: float):
        self.parameter_changed.emit("offset_current", QVariant(value))

    def go_next(self) -> Config:
        self._sweep_iteration += 1
        if self.sweep_freq and (self._sweep_iteration % self.sweep_freq) == 0:
            self.current_percentage = uniform(self.sweep_min, self.sweep_max)
        return {"current_percentage": self.current_percentage}

    @property
    def settings(self) -> Config:
        """
        Return a dict of settings for the PDM.
        """
        super_settings = super().settings
        super_settings.update(
            {
                "on_off": self.on_off,
                "current_percentage": self.current_percentage,
                "offset_current": self.offset_current,
                "sweep_max": self.sweep_max,
                "sweep_min": self.sweep_min,
                "sweep_freq": self.sweep_freq,
            }
        )
        return super_settings

    @settings.setter
    def settings(self, data: Config):
        """
        Set the settings of the PDM.
        """
        ProbeInstrument.settings.__set__(self, data)
        if "on_off" in data:
            self.on_off = bool(data["on_off"])
            self.parameter_changed.emit("on_off", data["on_off"])
        if "current_percentage" in data:
            current_percentage = data["current_percentage"]
            if isinstance(current_percentage, float):
                self.current_percentage = current_percentage
                self.parameter_changed.emit("current_percentage", current_percentage)
            else:
                logging.getLogger("laserstudio").warning(
                    f"Current percentage is not a float: {current_percentage}. Skipping."
                )
        if "offset_current" in data:
            offset_current = data["offset_current"]
            if isinstance(offset_current, float):
                self.offset_current = offset_current
                self.parameter_changed.emit("offset_current", offset_current)
            else:
                logging.getLogger("laserstudio").warning(
                    f"Offset current is not a float: {offset_current}. Skipping."
                )
        if "sweep_max" in data:
            sweep_max = data["sweep_max"]
            if isinstance(sweep_max, float):
                self.sweep_max = sweep_max
                self.parameter_changed.emit("sweep_max", sweep_max)
            else:
                logging.getLogger("laserstudio").warning(
                    f"Sweep max is not a float: {sweep_max}. Skipping."
                )
            self.parameter_changed.emit("sweep_max", data["sweep_max"])
        if "sweep_min" in data:
            sweep_min = data["sweep_min"]
            if isinstance(sweep_min, float):
                self.sweep_min = sweep_min
                self.parameter_changed.emit("sweep_min", sweep_min)
            else:
                logging.getLogger("laserstudio").warning(
                    f"Sweep min is not a float: {sweep_min}. Skipping."
                )
            self.parameter_changed.emit("sweep_min", data["sweep_min"])
        if "sweep_freq" in data:
            sweep_freq = data["sweep_freq"]
            if isinstance(sweep_freq, int):
                self.sweep_freq = int(sweep_freq)
                self.parameter_changed.emit("sweep_freq", sweep_freq)
            else:
                logging.getLogger("laserstudio").warning(
                    f"Sweep freq is not an integer: {sweep_freq}. Skipping."
                )
            self.parameter_changed.emit("sweep_freq", data["sweep_freq"])
