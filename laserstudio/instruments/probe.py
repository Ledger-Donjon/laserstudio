from PyQt6.QtCore import pyqtSignal
from typing import Any
from .instrument import Instrument
import logging


class ProbeInstrument(Instrument):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config=config)
        # Set manual position relative to the center position
        # of the camera, eg in the StageSight coordinates.
        self._offset_pos: tuple[float, float] | None = None
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
    def settings(self, data: dict[str, Any]):
        """Import settings from a dict."""
        assert Instrument.settings.fset is not None
        Instrument.settings.fset(self, data)
        offset_pos = data.get("offset_pos", None)
        self.offset_pos = tuple(offset_pos) if offset_pos is not None else None

    @property
    def offset_pos(self) -> tuple[float, float] | None:
        return self._offset_pos

    @offset_pos.setter
    def offset_pos(self, offset_pos: tuple[float, float] | None):
        self._offset_pos = offset_pos
        logging.getLogger("laserstudio").debug(f"Offset pos changed to {offset_pos}")
        self.offset_pos_changed.emit()
