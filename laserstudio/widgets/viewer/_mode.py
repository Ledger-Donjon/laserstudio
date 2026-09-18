from __future__ import annotations
from enum import Enum, auto


class Mode(int, Enum):
    """Viewer modes."""

    NONE = auto()
    STAGE = auto()
    ZONE = auto()
    ZONE_TILTED = auto()
    ZONE_POLY = auto()
    PIN = auto()
    OFFSET_ORIGIN = auto()
    RULER = auto()
    MARKER = auto()
    PROBE_OFFSET = auto()
