from __future__ import annotations
import logging
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor
from laserstudio.widgets.marker import IdMarker
from laserstudio.widgets.ruler import Ruler
from laserstudio.utils.colors import LedgerColors
from ._base import _ViewerBase


class _MarkersRulersMixin(_ViewerBase):
    """User-facing markers and rulers: creation, removal, defaults, and the
    interactive drag-to-create-a-ruler flow."""

    @property
    def markers(self) -> list[IdMarker]:
        return self.annotations_geometry.markers

    @property
    def markers_by_label_by_color(
        self,
    ) -> dict[str | None, dict[str, set[IdMarker]]]:
        return self.annotations_geometry.markers_by_label_by_color

    @property
    def default_marker_size(self) -> float:
        return self.annotations.default_marker_size

    @default_marker_size.setter
    def default_marker_size(self, value: float) -> None:
        self.annotations.default_marker_size = float(value)

    @property
    def default_marker_color(self) -> QColor:
        return self.annotations.default_marker_color

    @default_marker_color.setter
    def default_marker_color(self, value: QColor) -> None:
        self.annotations.default_marker_color = value

    @property
    def default_ruler_color(self) -> QColor:
        return self.annotations.default_ruler_color

    @default_ruler_color.setter
    def default_ruler_color(self, value: QColor) -> None:
        self.annotations.default_ruler_color = value

    @property
    def default_ruler_graduation(self) -> float | None:
        return self.annotations.default_ruler_graduation

    @default_ruler_graduation.setter
    def default_ruler_graduation(self, value: float | None) -> None:
        self.annotations.default_ruler_graduation = value

    def marker_size(self, value: float):
        self.annotations_geometry.apply_marker_size(value)
        self.setUpdatesEnabled(False)
        self.setUpdatesEnabled(True)

    def add_marker(
        self,
        position: None | tuple[float, float] | list[float] = None,
        color: QColor | Qt.GlobalColor | int | list[float] | LedgerColors | None = None,
        label: str | None = None,
        visible: bool = True,
        *,
        marker_id: int | None = None,
    ) -> IdMarker:
        """
        Add a marker at a specific position, or at current observed position.

        :param position: The position of the marker. If None, the position is retrieved from the stage's current position.
        :param color: The color of the marker. If None, the viewer's default is used.
        :param label: The label of the marker.
        :param visible: If False, the marker is created but not displayed (setVisible(False)).
        :return: The added marker.
        """
        # Creation of the marker
        if position is None:
            p = self.focused_element_position()
            position = p.x(), p.y()
        elif isinstance(position, list):
            position = (float(position[0]), float(position[1]))

        data = self.annotations.add_marker(
            position,
            color=color,
            label=label,
            visible=visible,
            marker_id=marker_id,
        )
        marker = self.annotations_geometry.get_marker(data.id)
        if marker is None:
            raise RuntimeError(f"Marker #{data.id} was not created in the view.")
        return marker

    def clear_markers(self):
        """Removes all markers."""
        self.annotations.clear_markers()

    def remove_marker(self, marker: IdMarker):
        """Remove a specific marker from the scene."""
        self.annotations.remove_marker(marker.id)
        logging.getLogger("laserstudio").info(f"Marker {marker} removed")

    # Rulers
    @property
    def rulers(self) -> list[Ruler]:
        return self.annotations_geometry.rulers

    def add_ruler(
        self,
        p1: tuple[float, float] | QPointF,
        p2: tuple[float, float] | QPointF,
        color: QColor | Qt.GlobalColor | int | list[float] | LedgerColors | None = None,
        label: str | None = None,
        graduation: float | None = None,
        graduation_count: float | None = None,
        visible: bool = True,
    ) -> Ruler:
        """
        Add a ruler measuring the distance between two positions.

        :param p1: The position of the first endpoint.
        :param p2: The position of the second endpoint.
        :param color: The color of the ruler. If None, the viewer's default is used.
        :param label: The label of the ruler.
        :param graduation: The graduation interval, in micrometers. If None, the
            ruler is drawn without graduations.
        :param graduation_count: The number of graduations wanted over the whole
            ruler, as an alternative to *graduation*: the ruler keeps that count
            and derives the interval from its length. Ignored when *graduation*
            is given.
        :param visible: If False, the ruler is created but not displayed.
        :return: The added ruler.
        """
        if isinstance(p1, QPointF):
            p1 = (p1.x(), p1.y())
        if isinstance(p2, QPointF):
            p2 = (p2.x(), p2.y())

        data = self.annotations.add_ruler(
            p1,
            p2,
            color=color,
            label=label,
            graduation=graduation,
            graduation_count=graduation_count,
            visible=visible,
        )
        ruler = self.annotations_geometry.get_ruler(data.id)
        if ruler is None:
            raise RuntimeError(f"Ruler #{data.id} was not created in the view.")
        return ruler

    def remove_ruler(self, ruler: Ruler):
        """Remove a specific ruler from the scene."""
        if ruler.id not in self.annotations.rulers:
            return
        self.annotations.remove_ruler(ruler.id)
        logging.getLogger("laserstudio").info(f"Ruler {ruler} removed")

    def clear_rulers(self):
        """Remove all rulers."""
        self.annotations.clear_rulers()

    def _start_ruler(self, scene_pos: QPointF):
        """Begin drawing a ruler; both endpoints start at the same position."""
        self._ruler_in_progress = self.add_ruler(scene_pos, scene_pos)

    def _finish_ruler(self):
        """Commit the ruler being drawn, or discard it if it is too short."""
        ruler = self._ruler_in_progress
        if ruler is None:
            return
        self._ruler_in_progress = None
        if ruler.length * self.zoom < self.MIN_RULER_DRAG_PIXELS:
            self.remove_ruler(ruler)
