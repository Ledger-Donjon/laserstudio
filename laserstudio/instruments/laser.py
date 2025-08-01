from .probe import ProbeInstrument
from random import uniform
from PyQt6.QtCore import QVariant
from .shutter import ShutterInstrument
from typing import Optional
from .lmscontroller import LMSControllerInstrument
import logging


class LaserInstrument(ProbeInstrument):
    def __init__(self, config: dict):
        super().__init__(config=config)
        # Sweep parameters, in order to change the current_percentage
        # regularly, within a random value from sweep_min to sweep_max,
        # each sweep_freq applications
        self.sweep_max = 100.0
        self.sweep_min = 0.0
        self.sweep_freq = 100
        self._sweep_iteration = 0

        # Shutter
        self.shutter: Optional[ShutterInstrument] = None
        shutter = config.get("shutter")
        if type(shutter) is dict and shutter.get("enable", True):
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

    def go_next(self) -> dict[str, float]:
        self._sweep_iteration += 1
        if self._sweep_iteration % self.sweep_freq == 0:
            self.current_percentage = uniform(self.sweep_min, self.sweep_max)
            return {"current_percentage": self.current_percentage}
        return {}

    @property
    def settings(self):
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
    def settings(self, data: dict):
        """
        Set the settings of the PDM.
        """
        ProbeInstrument.settings.__set__(self, data)
        if "on_off" in data:
            self.on_off = data["on_off"]
            self.parameter_changed.emit("on_off", data["on_off"])
        if "current_percentage" in data:
            self.current_percentage = data["current_percentage"]
            self.parameter_changed.emit(
                "current_percentage", data["current_percentage"]
            )
        if "offset_current" in data:
            self.offset_current = data["offset_current"]
            self.parameter_changed.emit("offset_current", data["offset_current"])
        if "sweep_max" in data:
            self.sweep_max = data["sweep_max"]
            self.parameter_changed.emit("sweep_max", data["sweep_max"])
        if "sweep_min" in data:
            self.sweep_min = data["sweep_min"]
            self.parameter_changed.emit("sweep_min", data["sweep_min"])
        if "sweep_freq" in data:
            self.sweep_freq = data["sweep_freq"]
            self.parameter_changed.emit("sweep_freq", data["sweep_freq"])
