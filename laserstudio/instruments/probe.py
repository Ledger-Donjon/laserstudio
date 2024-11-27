from PyQt6.QtCore import pyqtSignal
from typing import Optional, Any
from .instrument import Instrument


class ProbeInstrument(Instrument):
    def __init__(self, config: dict):
        super().__init__(config=config)
        # Set manual position relative to the center position
        # of the camera, eg in the StageSight coordinates.
        self._fixed_pos: Optional[tuple[float, float]] = None

    # Signal emited when fixed pos paremeter changed
    fixed_pos_changed = pyqtSignal()

    @property
    def yaml(self) -> dict[str, Any]:
        yaml = {}
        if self.fixed_pos is not None:
            yaml["fixed_pos"] = list(self.fixed_pos)
        return yaml

    @yaml.setter
    def yaml(self, yaml: dict):
        """Import settings from a dict."""
        fixed_pos = yaml.get("fixed_pos", None)
        self.fixed_pos = tuple(fixed_pos) if fixed_pos is not None else None

    @property
    def fixed_pos(self) -> Optional[tuple[float, float]]:
        return self._fixed_pos

    @fixed_pos.setter
    def fixed_pos(self, fixed_pos):
        self._fixed_pos = fixed_pos
        self.fixed_pos_changed.emit()
