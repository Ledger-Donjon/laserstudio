from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsRectItem,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from ..utils.colors import LedgerColors
from .softlimits import EDIT_HANDLE_ATTR


class _RadiusHandle(QGraphicsRectItem):
    """Constant-size square handle used to change the circle radius.

    All four handles behave identically: dragging any of them sets the radius to
    the distance between the circle center and the cursor.
    """

    SIZE = 12.0

    def __init__(self, owner: "MaxDistanceItem", angle_deg: float):
        super().__init__(-self.SIZE / 2, -self.SIZE / 2, self.SIZE, self.SIZE, owner)
        setattr(self, EDIT_HANDLE_ATTR, True)
        self._owner = owner
        self.angle_deg = angle_deg
        # Keep the handle at a constant pixel size whatever the view zoom.
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setZValue(1)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self._apply_style(hovered=False)

    def _apply_style(self, hovered: bool):
        color = (
            LedgerColors.SerenityPurple.value
            if hovered
            else LedgerColors.SerenityPurple.value.lighter(115)
        )
        pen = QPen(QColor(255, 255, 255))
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QBrush(color))

    def hoverEnterEvent(self, event):
        self._apply_style(hovered=True)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._apply_style(hovered=False)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent | None):
        if event is None:
            return
        # Accept the press so the view does not start panning and so this item
        # grabs the mouse for the subsequent move/release events.
        self._owner._dragging = True
        event.accept()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent | None):
        if event is None:
            return
        self._owner._resize_from_scene_pos(event.scenePos())
        event.accept()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent | None):
        if event is None:
            return
        self._owner._dragging = False
        self._owner._finish_edit()
        event.accept()


class MaxDistanceItem(QGraphicsObject):
    """Resizable circle representing the "Max move distance" guardrail.

    The circle is centered on the current stage position and its radius is the
    maximum allowed move distance (stage µm). Dragging any of the four handles
    changes the radius, which is written back to the stage guardrail.
    """

    # Emitted continuously while the user drags a handle (live update).
    radius_changed = pyqtSignal(float)
    # Emitted once when a resize gesture ends (mouse released).
    edit_finished = pyqtSignal(float)

    MIN_RADIUS = 1.0

    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._cx = 0.0
        self._cy = 0.0
        self._radius = 0.0
        # The body must not steal mouse clicks: clicks inside the circle (but not
        # on a handle) should still reach the viewer (e.g. for stage moves).
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setZValue(9)

        self._handles = [_RadiusHandle(self, a) for a in (0.0, 90.0, 180.0, 270.0)]
        self._reposition_handles()

        self._handles_shown = False
        self._dragging = False
        self._set_handles_shown(False)

    # -- Geometry ---------------------------------------------------------
    def radius(self) -> float:
        return self._radius

    def center(self) -> QPointF:
        return QPointF(self._cx, self._cy)

    def set_center(self, cx: float, cy: float) -> None:
        """Set the circle center (scene µm)."""
        self.prepareGeometryChange()
        self._cx = float(cx)
        self._cy = float(cy)
        self._reposition_handles()
        self.update()

    def set_radius(self, radius: float) -> None:
        """Set the circle radius (scene µm, clamped to a minimal value)."""
        self.prepareGeometryChange()
        self._radius = max(0.0, float(radius))
        self._reposition_handles()
        self.update()

    def boundingRect(self) -> QRectF:
        margin = _RadiusHandle.SIZE + 4.0
        size = 2.0 * (self._radius + margin)
        return QRectF(
            self._cx - self._radius - margin,
            self._cy - self._radius - margin,
            size,
            size,
        )

    def shape(self) -> QPainterPath:
        # The circle body is purely decorative and must not intercept clicks: its
        # default (bounding-rect) shape is a filled square that would shadow
        # underlying edit handles (e.g. the stage area limit handles) and swallow
        # stage moves. Only the handles (separate child items) are interactive.
        return QPainterPath()

    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = None,
    ) -> None:
        if painter is None:
            return
        pen = QPen(LedgerColors.SerenityPurple.value)
        pen.setCosmetic(True)
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(self._cx, self._cy), self._radius, self._radius)

    # -- Handles ----------------------------------------------------------
    def _set_handles_shown(self, shown: bool) -> None:
        if shown == self._handles_shown:
            return
        self._handles_shown = shown
        for handle in self._handles:
            handle.setVisible(shown)

    def update_cursor_proximity(
        self, scene_point: QPointF | None, threshold: float
    ) -> None:
        """Show the handles when the cursor is close to the circle border."""
        if self._dragging:
            return
        if scene_point is None:
            self._set_handles_shown(False)
            return
        distance = math.hypot(scene_point.x() - self._cx, scene_point.y() - self._cy)
        self._set_handles_shown(abs(distance - self._radius) <= threshold)

    def _reposition_handles(self) -> None:
        for handle in self._handles:
            angle = math.radians(handle.angle_deg)
            handle.setPos(
                QPointF(
                    self._cx + self._radius * math.cos(angle),
                    self._cy + self._radius * math.sin(angle),
                )
            )

    def _resize_from_scene_pos(self, scene_pos: QPointF) -> None:
        radius = math.hypot(scene_pos.x() - self._cx, scene_pos.y() - self._cy)
        radius = max(self.MIN_RADIUS, radius)
        self.set_radius(radius)
        self.radius_changed.emit(radius)

    def _finish_edit(self) -> None:
        self.edit_finished.emit(self._radius)
