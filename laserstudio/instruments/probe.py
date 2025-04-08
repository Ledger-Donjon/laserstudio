from PyQt6.QtCore import pyqtSignal
from typing import Optional, Any
from .instrument import Instrument


class ProbeInstrument(Instrument):
    def __init__(self, config: dict):
        super().__init__(config=config)
        # Set manual position relative to the center position
        # of the camera, eg in the StageSight coordinates.
        self._offset_pos: Optional[tuple[float, float]] = None
        if "offset_pos" in config:
            self._offset_pos = tuple(config["offset_pos"])

    # Signal emited when fixed pos parameter changed
    offset_pos_changed = pyqtSignal()

    @property
    def settings(self) -> dict[str, Any]:
        data = super().settings
        if self.offset_pos is not None:
            data["offset_pos"] = list(self.offset_pos)
        return data

    @settings.setter
    def settings(self, data: dict):
        """Import settings from a dict."""
        assert Instrument.settings.fset is not None
        Instrument.settings.fset(self, data)
        offset_pos = data.get("offset_pos", None)
        self.offset_pos = tuple(offset_pos) if offset_pos is not None else None

    @property
    def offset_pos(self) -> Optional[tuple[float, float]]:
        return self._offset_pos

    @offset_pos.setter
    def offset_pos(self, offset_pos):
        self._offset_pos = offset_pos
        self.offset_pos_changed.emit()
