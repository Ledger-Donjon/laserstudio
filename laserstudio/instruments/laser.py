from .probe import ProbeInstrument
from random import uniform


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

    @property
    def yaml(self) -> dict:
        """Export settings to a dict for yaml serialization."""
        yaml = super().yaml
        yaml["sweep_max"] = self.sweep_max
        yaml["sweep_min"] = self.sweep_min
        yaml["sweep_freq"] = self.sweep_freq
        return yaml

    @yaml.setter
    def yaml(self, yaml: dict):
        """Import settings from a dict."""
        assert ProbeInstrument.yaml.fset is not None
        ProbeInstrument.yaml.fset(self, yaml)
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

    def go_next(self):
        self._sweep_iteration += 1
        if self._sweep_iteration % self.sweep_freq == 0:
            self.current_percentage = uniform(self.sweep_min, self.sweep_max)
