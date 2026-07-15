from __future__ import annotations

from PyQt6.QtCore import QVariant

from .laser import LaserInstrument
from ..utils.yaml_types import Config


class LaserDummy(LaserInstrument):
    """Dummy laser keeping its state in memory.

    Useful to run and test Laser Studio without any real laser hardware. It
    implements the basic laser features (``on_off``, ``current_percentage``,
    ``offset_current``) by simply storing their values, and reuses the sweep
    behaviour of :class:`LaserInstrument` for ``go_next``.
    """

    def __init__(self, config: Config):
        """
        :param config: YAML configuration object
        """
        super().__init__(config=config)
        self._on_off = False
        self._current_percentage = 0.0
        self._offset_current = 0.0

    @property
    def on_off(self) -> bool:
        return self._on_off

    @on_off.setter
    def on_off(self, value: bool):
        self._on_off = bool(value)
        self.parameter_changed.emit("on_off", QVariant(value))

    @property
    def current_percentage(self) -> float:
        return self._current_percentage

    @current_percentage.setter
    def current_percentage(self, value: float):
        self._current_percentage = float(value)
        self.parameter_changed.emit("current_percentage", QVariant(value))

    @property
    def offset_current(self) -> float:
        return self._offset_current

    @offset_current.setter
    def offset_current(self, value: float):
        self._offset_current = float(value)
        self.parameter_changed.emit("offset_current", QVariant(value))
