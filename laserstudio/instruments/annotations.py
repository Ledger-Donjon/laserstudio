from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QColorConstants

from ..utils.colors import LedgerColors
from ..utils.yaml_types import Config
from .instrument import Instrument

__all__ = ["AnnotationsInstrument", "RulerAnnotation", "MarkerAnnotation"]


def _color_to_list(color: QColor) -> list[float]:
    return [color.redF(), color.greenF(), color.blueF(), color.alphaF()]


def _list_to_qcolor(
    color: QColor | Qt.GlobalColor | int | list[float] | LedgerColors,
) -> QColor:
    if isinstance(color, LedgerColors):
        return QColor(color.value)
    if isinstance(color, list):
        alpha = color[3] if len(color) > 3 else 1.0
        return QColor(
            int(color[0] * 255),
            int(color[1] * 255),
            int(color[2] * 255),
            int(alpha * 255),
        )
    return QColor(color)


@dataclass
class RulerAnnotation:
    """Data model for a distance ruler, without graphics."""

    id: int
    p1: tuple[float, float]
    p2: tuple[float, float]
    color: list[float]
    label: str | None = None
    graduation: float | None = None
    graduation_count: float | None = None
    visible: bool = True

    @property
    def length(self) -> float:
        return math.hypot(self.p2[0] - self.p1[0], self.p2[1] - self.p1[1])

    def to_dict(self) -> Config:
        data: Config = {
            "id": self.id,
            "p1": [self.p1[0], self.p1[1]],
            "p2": [self.p2[0], self.p2[1]],
            "length": self.length,
            "color": list(self.color),
        }
        if not self.visible:
            data["hidden"] = True
        if self.label is not None:
            data["label"] = self.label
        if self.graduation is not None:
            data["graduation"] = self.graduation
        if self.graduation_count is not None:
            data["graduation_count"] = self.graduation_count
        return data

    @classmethod
    def from_dict(cls, data: Config, *, fallback_id: int) -> RulerAnnotation:
        p1 = data.get("p1", [0.0, 0.0])
        p2 = data.get("p2", [0.0, 0.0])
        raw_id = data.get("id")
        ruler_id = (
            int(raw_id)
            if isinstance(raw_id, int) and not isinstance(raw_id, bool)
            else fallback_id
        )
        color = data.get("color", [1.0, 1.0, 0.0, 1.0])
        if not isinstance(color, list):
            color = [1.0, 1.0, 0.0, 1.0]
        graduation = data.get("graduation")
        graduation_count = data.get("graduation_count")
        return cls(
            id=ruler_id,
            p1=(float(p1[0]), float(p1[1])),
            p2=(float(p2[0]), float(p2[1])),
            color=[float(c) for c in color],
            label=data.get("label"),
            graduation=float(graduation) if graduation else None,
            graduation_count=float(graduation_count) if graduation_count else None,
            visible=not data.get("hidden", False),
        )


@dataclass
class MarkerAnnotation:
    """Data model for a user-placed marker, without graphics."""

    id: int
    pos: tuple[float, float]
    color: list[float]
    label: str | None = None
    visible: bool = True

    def to_dict(self) -> Config:
        data: Config = {
            "id": self.id,
            "pos": [self.pos[0], self.pos[1]],
            "color": list(self.color),
        }
        if not self.visible:
            data["hidden"] = True
        if self.label is not None:
            data["label"] = self.label
        return data

    @classmethod
    def from_dict(cls, data: Config, *, fallback_id: int) -> MarkerAnnotation:
        pos = data.get("pos", [0.0, 0.0])
        raw_id = data.get("id")
        marker_id = (
            int(raw_id)
            if isinstance(raw_id, int) and not isinstance(raw_id, bool)
            else fallback_id
        )
        color = data.get("color", [1.0, 0.0, 0.0, 1.0])
        if not isinstance(color, list):
            color = [1.0, 0.0, 0.0, 1.0]
        return cls(
            id=marker_id,
            pos=(float(pos[0]), float(pos[1])),
            color=[float(c) for c in color],
            label=data.get("label"),
            visible=not data.get("hidden", False),
        )


class AnnotationsInstrument(Instrument):
    """Shared model for rulers and user markers.

    Holds no graphics, so one instance can drive several viewers (classic and
    new UI). Views subscribe to :attr:`rulers_changed` and
    :attr:`markers_changed`.
    """

    rulers_changed = pyqtSignal(int)
    markers_changed = pyqtSignal(int)

    def __init__(self, config: Config):
        super().__init__(config)
        self.rulers: dict[int, RulerAnnotation] = {}
        self.markers: dict[int, MarkerAnnotation] = {}
        self._ruler_id_seq = 1
        self._marker_id_seq = 1
        self._default_marker_size = 20.0
        self._default_ruler_color = QColor(LedgerColors.Grellow.value)
        self._default_ruler_graduation: float | None = None

    # -- Defaults --------------------------------------------------------- #

    @property
    def default_marker_size(self) -> float:
        return self._default_marker_size

    @default_marker_size.setter
    def default_marker_size(self, value: float) -> None:
        self._default_marker_size = float(value)
        self.markers_changed.emit(-1)

    @property
    def default_ruler_color(self) -> QColor:
        return QColor(self._default_ruler_color)

    @default_ruler_color.setter
    def default_ruler_color(self, value: QColor) -> None:
        self._default_ruler_color = QColor(value)

    @property
    def default_ruler_graduation(self) -> float | None:
        return self._default_ruler_graduation

    @default_ruler_graduation.setter
    def default_ruler_graduation(self, value: float | None) -> None:
        self._default_ruler_graduation = value if value and value > 0 else None

    # -- Rulers ----------------------------------------------------------- #

    def _allocate_ruler_id(self) -> int:
        while self._ruler_id_seq in self.rulers:
            self._ruler_id_seq += 1
        rid = self._ruler_id_seq
        self._ruler_id_seq = rid + 1
        return rid

    def add_ruler(
        self,
        p1: tuple[float, float],
        p2: tuple[float, float],
        color: QColor
        | Qt.GlobalColor
        | int
        | list[float]
        | LedgerColors
        | None = None,
        label: str | None = None,
        graduation: float | None = None,
        graduation_count: float | None = None,
        visible: bool = True,
        *,
        ruler_id: int | None = None,
    ) -> RulerAnnotation:
        if color is None:
            color = self._default_ruler_color
        if graduation is None and not graduation_count:
            graduation = self._default_ruler_graduation

        qcolor = _list_to_qcolor(color)
        stored_graduation = graduation if graduation and graduation > 0 else None
        stored_count = None
        if stored_graduation is None and graduation_count and graduation_count > 0:
            stored_count = float(graduation_count)

        rid = ruler_id if ruler_id is not None else self._allocate_ruler_id()
        if rid in self.rulers:
            raise ValueError(f"Ruler with id {rid} already exists.")

        ruler = RulerAnnotation(
            id=rid,
            p1=(float(p1[0]), float(p1[1])),
            p2=(float(p2[0]), float(p2[1])),
            color=_color_to_list(qcolor),
            label=label,
            graduation=stored_graduation,
            graduation_count=stored_count,
            visible=visible,
        )
        self.rulers[rid] = ruler
        self._ruler_id_seq = max(self._ruler_id_seq, rid + 1)
        self.rulers_changed.emit(rid)
        return ruler

    def update_ruler(self, ruler: RulerAnnotation) -> None:
        if ruler.id not in self.rulers:
            return
        self.rulers[ruler.id] = ruler
        self.rulers_changed.emit(ruler.id)

    def remove_ruler(self, ruler_id: int) -> None:
        if ruler_id not in self.rulers:
            return
        del self.rulers[ruler_id]
        self.rulers_changed.emit(ruler_id)

    def clear_rulers(self) -> None:
        if not self.rulers:
            return
        self.rulers.clear()
        self.rulers_changed.emit(-1)

    # -- Markers ---------------------------------------------------------- #

    def _allocate_marker_id(self) -> int:
        while self._marker_id_seq in self.markers:
            self._marker_id_seq += 1
        mid = self._marker_id_seq
        self._marker_id_seq = mid + 1
        return mid

    def add_marker(
        self,
        pos: tuple[float, float],
        color: QColor
        | Qt.GlobalColor
        | int
        | list[float]
        | LedgerColors = QColorConstants.Red,
        label: str | None = None,
        visible: bool = True,
        *,
        marker_id: int | None = None,
    ) -> MarkerAnnotation:
        mid = marker_id if marker_id is not None else self._allocate_marker_id()
        if mid in self.markers:
            raise ValueError(f"Marker with id {mid} already exists.")

        marker = MarkerAnnotation(
            id=mid,
            pos=(float(pos[0]), float(pos[1])),
            color=_color_to_list(_list_to_qcolor(color)),
            label=label,
            visible=visible,
        )
        self.markers[mid] = marker
        self._marker_id_seq = max(self._marker_id_seq, mid + 1)
        self.markers_changed.emit(mid)
        return marker

    def update_marker(self, marker: MarkerAnnotation) -> None:
        if marker.id not in self.markers:
            return
        self.markers[marker.id] = marker
        self.markers_changed.emit(marker.id)

    def remove_marker(self, marker_id: int) -> None:
        if marker_id not in self.markers:
            return
        del self.markers[marker_id]
        self.markers_changed.emit(marker_id)

    def clear_markers(self) -> None:
        if not self.markers:
            return
        self.markers.clear()
        self.markers_changed.emit(-1)

    # -- Persistence ------------------------------------------------------ #

    @property
    def settings(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "marker_size": self.default_marker_size,
            "default_ruler_color": _color_to_list(self.default_ruler_color),
            "default_ruler_graduation": self.default_ruler_graduation,
        }
        if self.rulers:
            data["rulers"] = [ruler.to_dict() for ruler in self.rulers.values()]
        if self.markers:
            data["markers"] = [marker.to_dict() for marker in self.markers.values()]
        return data

    @settings.setter
    def settings(self, data: dict[str, Any]) -> None:
        logging.getLogger("laserstudio").debug(f"Annotations settings: {data}...")

        marker_size = data.get("marker_size")
        if isinstance(marker_size, (int, float)) and not isinstance(marker_size, bool):
            self._default_marker_size = float(marker_size)

        color = data.get("default_ruler_color")
        if isinstance(color, list) and len(color) >= 3:
            self._default_ruler_color = _list_to_qcolor(color)

        graduation = data.get("default_ruler_graduation")
        if graduation is None or (
            isinstance(graduation, (int, float)) and not isinstance(graduation, bool)
        ):
            self._default_ruler_graduation = (
                float(graduation) if graduation and graduation > 0 else None
            )

        rulers_data = data.get("rulers")
        if isinstance(rulers_data, list):
            new_rulers: dict[int, RulerAnnotation] = {}
            for index, item in enumerate(rulers_data):
                if not isinstance(item, dict):
                    continue
                try:
                    ruler = RulerAnnotation.from_dict(item, fallback_id=index + 1)
                    new_rulers[ruler.id] = ruler
                except Exception:
                    logging.getLogger("laserstudio").warning(
                        f"Skipping malformed ruler entry: {item=}"
                    )
            self.rulers.clear()
            self.rulers.update(new_rulers)
            if new_rulers:
                self._ruler_id_seq = max(new_rulers.keys()) + 1
            self.rulers_changed.emit(-1)

        markers_data = data.get("markers")
        if isinstance(markers_data, list):
            new_markers: dict[int, MarkerAnnotation] = {}
            for index, item in enumerate(markers_data):
                if not isinstance(item, dict):
                    continue
                try:
                    marker = MarkerAnnotation.from_dict(item, fallback_id=index + 1)
                    new_markers[marker.id] = marker
                except Exception:
                    logging.getLogger("laserstudio").warning(
                        f"Skipping malformed marker entry: {item=}"
                    )
            self.markers.clear()
            self.markers.update(new_markers)
            if new_markers:
                self._marker_id_seq = max(new_markers.keys()) + 1
            self.markers_changed.emit(-1)
