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
        spot_size = config.get("spot_size_um", config.get("spot_size"))
        self._spot_size_um = float(spot_size) if spot_size is not None else 10.0

    # Signal emited when fixed pos parameter changed
    offset_pos_changed = pyqtSignal()
    spot_size_changed = pyqtSignal()

    @property
    def settings(self) -> dict[str, Any]:
        data = super().settings
        if self.offset_pos is not None:
            data["offset_pos"] = list(self.offset_pos)
        data["spot_size_um"] = self.spot_size_um
        return data

    @settings.setter
    def settings(self, data: dict[str, Any]):
        """Import settings from a dict."""
        assert Instrument.settings.fset is not None
        Instrument.settings.fset(self, data)
        offset_pos = data.get("offset_pos", None)
        self.offset_pos = tuple(offset_pos) if offset_pos is not None else None
        if "spot_size_um" in data:
            self.spot_size_um = data["spot_size_um"]
        elif "spot_size" in data:
            self.spot_size_um = data["spot_size"]

    @property
    def offset_pos(self) -> tuple[float, float] | None:
        return self._offset_pos

    @offset_pos.setter
    def offset_pos(self, offset_pos: tuple[float, float] | None):
        self._offset_pos = offset_pos
        logging.getLogger("laserstudio").debug(f"Offset pos changed to {offset_pos}")
        self.offset_pos_changed.emit()

    @property
    def spot_size_um(self) -> float:
        return self._spot_size_um

    @spot_size_um.setter
    def spot_size_um(self, value: float):
        if value <= 0:
            raise ValueError("Spot size must be positive")
        self._spot_size_um = value
        logging.getLogger("laserstudio").debug(f"Spot size changed to {value}")
        self.spot_size_changed.emit()
