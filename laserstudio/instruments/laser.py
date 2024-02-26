from PyQt6.QtCore import QObject
from typing import Tuple, Optional


class LaserInstrument(QObject):
    def __init__(self, config: dict):
        super().__init__()

        # Set manual position relative to the center position
        # of the camera, in the StageSight coordinates.
        self.fixed_pos: Optional[Tuple[float, float]] = None

        # Sweep parameters, in order to change the current_percentage
        # regularly, within a random value from sweep_min to sweep_max,
        # each sweep_freq applications
        self.sweep_max = 100.0
        self.sweep_min = 0.0
        self.sweep_freq = 100

    @property
    def yaml(self) -> dict:
        """Export settings to a dict for yaml serialization."""
        yaml = {}
        if self.fixed_pos is not None:
            yaml["fixed_pos"] = list(self.fixed_pos)

        yaml["sweep_max"] = self.sweep_max
        yaml["sweep_min"] = self.sweep_min
        yaml["sweep_freq"] = self.sweep_freq
        return yaml

    @yaml.setter
    def yaml(self, yaml: dict):
        """Import settings from a dict."""
        fixed_pos = yaml.get("fixed_pos", None)
        self.fixed_pos = tuple(fixed_pos) if fixed_pos is not None else None

        self.sweep_max = yaml.get("sweep_max", self.sweep_max)
        self.sweep_min = yaml.get("sweep_min", self.sweep_min)
        self.sweep_freq = yaml.get("sweep_freq", self.sweep_freq)

    @property
    def on_off(self) -> bool: ...

    @on_off.setter
    def on_off(self, value: bool): ...

    @property
    def current_percentage(self) -> float: ...

    @current_percentage.setter
    def current_percentage(self, value: float): ...

    @property
    def offset_current(self) -> float: ...

    @offset_current.setter
    def offset_current(self, value: float): ...
