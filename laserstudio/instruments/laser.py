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
    def settings(self) -> dict:
        """Export settings to a dict for yaml serialization."""
        settings = super().settings
        settings["sweep_max"] = self.sweep_max
        settings["sweep_min"] = self.sweep_min
        settings["sweep_freq"] = self.sweep_freq
        return settings

    @settings.setter
    def settings(self, data: dict):
        """Import settings from a dict."""
        ProbeInstrument.settings.__set__(self, data)
        self.sweep_max = data.get("sweep_max", self.sweep_max)
        self.sweep_min = data.get("sweep_min", self.sweep_min)
        self.sweep_freq = data.get("sweep_freq", self.sweep_freq)

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
