from PyQt6.QtCore import QObject
from typing import Tuple, Optional, Any


class ProbeInstrument(QObject):
    def __init__(self, config: dict):
        super().__init__()
        # Set manual position relative to the center position
        # of the camera, eg in the StageSight coordinates.
        self.fixed_pos: Optional[Tuple[float, float]] = None

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
