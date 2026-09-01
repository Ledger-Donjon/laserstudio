from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QGraphicsItemGroup

from ..instruments.annotations import (
    AnnotationsInstrument,
    MarkerAnnotation,
    RulerAnnotation,
    _list_to_qcolor,
)
from ..utils.colors import LedgerColors
from .marker import IdMarker
from .ruler import Ruler

if TYPE_CHECKING:
    from .viewer import Viewer


class AnnotationsGeometry(QGraphicsItemGroup):
    """Scene representation of an :class:`AnnotationsInstrument`.

    Each viewer owns one instance; several instances can render the same
    shared model (classic and new UI).
    """

    def __init__(
        self,
        annotations: AnnotationsInstrument,
        viewer: Viewer,
        parent=None,
    ):
        super().__init__(parent)
        self.annotations = annotations
        self.viewer = viewer
        self._rulers: dict[int, Ruler] = {}
        self._markers: dict[int, IdMarker] = {}
        self._ruler_handlers: dict[int, Callable[[], None]] = {}
        self._marker_handlers: dict[int, Callable[[], None]] = {}
        self._syncing = False

        annotations.rulers_changed.connect(self._on_rulers_changed)
        annotations.markers_changed.connect(self._on_markers_changed)
        self._sync_all_rulers()
        self._sync_all_markers()

    # -- Rulers ----------------------------------------------------------- #

    @property
    def rulers(self) -> list[Ruler]:
        return list(self._rulers.values())

    def get_ruler(self, ruler_id: int) -> Ruler | None:
        return self._rulers.get(ruler_id)

    def get_marker(self, marker_id: int) -> IdMarker | None:
        return self._markers.get(marker_id)

    def _on_rulers_changed(self, ruler_id: int) -> None:
        if ruler_id < 0:
            self._sync_all_rulers()
            return
        if ruler_id not in self.annotations.rulers:
            self._remove_ruler_graphics(ruler_id)
            return
        self._sync_ruler(ruler_id)

    def _sync_all_rulers(self) -> None:
        for rid in list(self._rulers.keys()):
            if rid not in self.annotations.rulers:
                self._remove_ruler_graphics(rid)
        for rid in self.annotations.rulers:
            self._sync_ruler(rid)

    def _sync_ruler(self, ruler_id: int) -> None:
        data = self.annotations.rulers.get(ruler_id)
        if data is None:
            self._remove_ruler_graphics(ruler_id)
            return

        ruler = self._rulers.get(ruler_id)
        if ruler is None:
            ruler = self._create_ruler_graphics(data)
            self._rulers[ruler_id] = ruler
            return

        self._apply_ruler_data(ruler, data)

    def _create_ruler_graphics(self, data: RulerAnnotation) -> Ruler:
        ruler = Ruler(
            data.p1,
            data.p2,
            viewer=self.viewer,
            color=data.color,
            label=data.label,
            graduation=data.graduation,
            graduation_count=data.graduation_count,
            ruler_id=data.id,
        )
        ruler.setVisible(data.visible)
        handler = partial(self._push_ruler_to_model, ruler)
        ruler.changed.connect(handler)
        self._ruler_handlers[data.id] = handler
        scene = self.viewer.scene()
        if scene is not None:
            scene.addItem(ruler)
        return ruler

    def _apply_ruler_data(self, ruler: Ruler, data: RulerAnnotation) -> None:
        self._syncing = True
        try:
            ruler.set_endpoint(0, QPointF(*data.p1))
            ruler.set_endpoint(1, QPointF(*data.p2))
            ruler.set_color(_list_to_qcolor(data.color))
            ruler.label = data.label
            if data.graduation is not None:
                ruler.graduation = data.graduation
            elif data.graduation_count is not None:
                ruler.graduation_count = data.graduation_count
            else:
                ruler.graduation = None
            ruler.setVisible(data.visible)
        finally:
            self._syncing = False

    def _remove_ruler_graphics(self, ruler_id: int) -> None:
        ruler = self._rulers.pop(ruler_id, None)
        if ruler is None:
            return
        handler = self._ruler_handlers.pop(ruler_id, None)
        if handler is not None:
            try:
                ruler.changed.disconnect(handler)
            except TypeError:
                pass
        scene = self.viewer.scene()
        if scene is not None:
            scene.removeItem(ruler)
        ruler.viewer = None

    def _push_ruler_to_model(self, ruler: Ruler) -> None:
        if self._syncing:
            return
        data = self.annotations.rulers.get(ruler.id)
        if data is None:
            return
        data.p1 = (ruler._p1.x(), ruler._p1.y())
        data.p2 = (ruler._p2.x(), ruler._p2.y())
        data.color = [
            ruler._color.redF(),
            ruler._color.greenF(),
            ruler._color.blueF(),
            ruler._color.alphaF(),
        ]
        data.label = ruler.label
        data.graduation = ruler.graduation
        data.graduation_count = ruler.graduation_count
        data.visible = ruler.isVisible()
        self.annotations.update_ruler(data)

    # -- Markers ---------------------------------------------------------- #

    @property
    def markers(self) -> list[IdMarker]:
        return list(self._markers.values())

    @property
    def markers_by_label_by_color(self) -> dict[str | None, dict[str, set[IdMarker]]]:
        result: dict[str | None, dict[str, set[IdMarker]]] = {None: {}}
        for marker in self._markers.values():
            label = marker.label
            if label not in result:
                result[label] = {}
            color_name = marker.color_name
            if color_name not in result[label]:
                result[label][color_name] = set()
            result[label][color_name].add(marker)
        return result

    def _on_markers_changed(self, marker_id: int) -> None:
        if marker_id < 0:
            self._sync_all_markers()
            return
        if marker_id not in self.annotations.markers:
            self._remove_marker_graphics(marker_id)
            return
        self._sync_marker(marker_id)

    def _sync_all_markers(self) -> None:
        for mid in list(self._markers.keys()):
            if mid not in self.annotations.markers:
                self._remove_marker_graphics(mid)
        for mid in self.annotations.markers:
            self._sync_marker(mid)
        self._apply_marker_size()

    def _sync_marker(self, marker_id: int) -> None:
        data = self.annotations.markers.get(marker_id)
        if data is None:
            self._remove_marker_graphics(marker_id)
            return

        marker = self._markers.get(marker_id)
        if marker is None:
            marker = self._create_marker_graphics(data)
            self._markers[marker_id] = marker
            return

        self._apply_marker_data(marker, data)

    def _create_marker_graphics(self, data: MarkerAnnotation) -> IdMarker:
        marker = IdMarker(
            viewer=self.viewer,
            color=data.color,
            label=data.label,
            position=data.pos,
            marker_id=data.id,
        )
        marker.setVisible(data.visible)
        marker.size = self.annotations.default_marker_size
        handler = partial(self._push_marker_to_model, marker)
        marker.set_position_changed_callback(handler)
        self._marker_handlers[data.id] = handler
        scene = self.viewer.scene()
        if scene is not None:
            scene.addItem(marker)
        return marker

    def _apply_marker_data(self, marker: IdMarker, data: MarkerAnnotation) -> None:
        self._syncing = True
        try:
            marker.setPos(QPointF(*data.pos))
            marker.set_color(_list_to_qcolor(data.color))
            marker.label = data.label
            marker.setVisible(data.visible)
            marker.size = self.annotations.default_marker_size
        finally:
            self._syncing = False

    def _remove_marker_graphics(self, marker_id: int) -> None:
        marker = self._markers.pop(marker_id, None)
        if marker is None:
            return
        handler = self._marker_handlers.pop(marker_id, None)
        if handler is not None:
            marker.set_position_changed_callback(None)
        scene = self.viewer.scene()
        if scene is not None:
            scene.removeItem(marker)
        marker.viewer = None

    def _push_marker_to_model(self, marker: IdMarker) -> None:
        if self._syncing:
            return
        data = self.annotations.markers.get(marker.id)
        if data is None:
            return
        pos = marker.pos()
        data.pos = (pos.x(), pos.y())
        self.annotations.update_marker(data)

    def _apply_marker_size(self) -> None:
        size = self.annotations.default_marker_size
        for marker in self._markers.values():
            marker.size = size

    def apply_marker_size(self, size: float) -> None:
        self.annotations.default_marker_size = size
