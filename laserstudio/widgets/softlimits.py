from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsRectItem,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from ..utils.colors import LedgerColors

# Generic marker attribute used by the Viewer to detect that a pressed item is
# an interactive edit handle (resize/reshape) and must keep its own mouse
# handling, instead of triggering a stage move or a zone creation.
EDIT_HANDLE_ATTR = "is_edit_handle"

# Kept for backward compatibility; both attributes are set on soft-limit handles.
SOFT_LIMIT_HANDLE_ATTR = EDIT_HANDLE_ATTR


class _SoftLimitHandle(QGraphicsRectItem):
    """A small, constant-size square handle used to resize the limit box.

    ``x_edge`` and ``y_edge`` indicate which edges of the box this handle
    controls: ``"min"``, ``"max"`` or ``None`` (axis not affected).
    """

    SIZE = 12.0

    def __init__(
        self,
        owner: "SoftLimitsItem",
        x_edge: str | None,
        y_edge: str | None,
    ):
        super().__init__(
            -self.SIZE / 2, -self.SIZE / 2, self.SIZE, self.SIZE, owner
        )
        setattr(self, EDIT_HANDLE_ATTR, True)
        self._owner = owner
        self.x_edge = x_edge
        self.y_edge = y_edge
        # Keep the handle at a constant pixel size whatever the view zoom.
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setZValue(1)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setAcceptHoverEvents(True)
        self._apply_style(hovered=False)
        self._update_cursor()

    def _apply_style(self, hovered: bool):
        color = (
            LedgerColors.SafetyOrange.value
            if hovered
            else LedgerColors.SafetyOrangeLight.value
        )
        pen = QPen(QColor(255, 255, 255))
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QBrush(color))

    def _update_cursor(self):
        if self.x_edge is not None and self.y_edge is not None:
            # Corner handles. The displayed diagonal depends on which corner,
            # but a simple size-all cursor is good enough and unambiguous.
            cursor = Qt.CursorShape.SizeAllCursor
        elif self.x_edge is not None:
            cursor = Qt.CursorShape.SizeHorCursor
        else:
            cursor = Qt.CursorShape.SizeVerCursor
        self.setCursor(cursor)

    def hoverEnterEvent(self, event):
        self._apply_style(hovered=True)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._apply_style(hovered=False)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent | None):
        if event is None:
            return
        # Accept the press so the view does not start panning/rubber-band and so
        # this item grabs the mouse for the subsequent move/release events.
        self._owner._dragging = True
        event.accept()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent | None):
        if event is None:
            return
        self._owner._resize_from_handle(self, event.scenePos())
        event.accept()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent | None):
        if event is None:
            return
        self._owner._dragging = False
        self._owner._finish_edit()
        event.accept()


class SoftLimitsItem(QGraphicsObject):
    """Resizable rectangle representing the X/Y software limit box.

    Coordinates are expressed in the scene (stage µm) referential. The box can
    be resized by dragging the handles placed on its corners and edges.
    """

    # Emitted continuously while the user drags a handle (live update).
    rect_changed = pyqtSignal(QRectF)
    # Emitted once when a resize gesture ends (mouse released).
    edit_finished = pyqtSignal(QRectF)

    MIN_SIZE = 1.0

    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._xmin = 0.0
        self._xmax = 0.0
        self._ymin = 0.0
        self._ymax = 0.0
        # The body must not steal mouse clicks: clicks inside the box (but not on
        # a handle) should still reach the viewer (e.g. for stage moves).
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setZValue(9)

        self._handles: list[_SoftLimitHandle] = []
        for x_edge, y_edge in (
            ("min", "min"),
            ("max", "min"),
            ("min", "max"),
            ("max", "max"),
            ("min", None),
            ("max", None),
            (None, "min"),
            (None, "max"),
        ):
            self._handles.append(_SoftLimitHandle(self, x_edge, y_edge))
        self._reposition_handles()

        # Handles are hidden by default (only the outline is shown) and appear
        # when the cursor gets close to the box border, to reduce visual clutter.
        self._handles_shown = False
        self._dragging = False
        self._set_handles_shown(False)

    # -- Geometry ---------------------------------------------------------
    def rect(self) -> QRectF:
        return QRectF(
            self._xmin,
            self._ymin,
            self._xmax - self._xmin,
            self._ymax - self._ymin,
        )

    def set_bounds(
        self, xmin: float, ymin: float, xmax: float, ymax: float
    ) -> None:
        """Set the box bounds (scene µm). Values are normalized so min <= max."""
        self.prepareGeometryChange()
        self._xmin, self._xmax = sorted((float(xmin), float(xmax)))
        self._ymin, self._ymax = sorted((float(ymin), float(ymax)))
        self._reposition_handles()
        self.update()

    def boundingRect(self) -> QRectF:
        # Add a small margin for the pen width.
        return self.rect().adjusted(-2.0, -2.0, 2.0, 2.0)

    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = None,
    ) -> None:
        if painter is None:
            return
        rect = self.rect()
        pen = QPen(LedgerColors.SafetyOrange.value)
        pen.setCosmetic(True)
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

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
        """Show the handles when the cursor is close to the box border.

        :param scene_point: cursor position in scene coordinates, or None when
            the cursor left the view.
        :param threshold: distance (scene units) within which handles appear.
        """
        if self._dragging:
            # Keep the handles visible during an active resize.
            return
        if scene_point is None:
            self._set_handles_shown(False)
            return
        rect = self.rect()
        outer = rect.adjusted(-threshold, -threshold, threshold, threshold)
        inner = rect.adjusted(threshold, threshold, -threshold, -threshold)
        near_border = outer.contains(scene_point) and not (
            inner.width() > 0 and inner.height() > 0 and inner.contains(scene_point)
        )
        self._set_handles_shown(near_border)

    def _reposition_handles(self) -> None:
        cx = (self._xmin + self._xmax) / 2.0
        cy = (self._ymin + self._ymax) / 2.0
        for handle in self._handles:
            x = cx if handle.x_edge is None else (
                self._xmin if handle.x_edge == "min" else self._xmax
            )
            y = cy if handle.y_edge is None else (
                self._ymin if handle.y_edge == "min" else self._ymax
            )
            handle.setPos(QPointF(x, y))

    def _resize_from_handle(
        self, handle: _SoftLimitHandle, scene_pos: QPointF
    ) -> None:
        xmin, xmax = self._xmin, self._xmax
        ymin, ymax = self._ymin, self._ymax
        if handle.x_edge == "min":
            xmin = scene_pos.x()
        elif handle.x_edge == "max":
            xmax = scene_pos.x()
        if handle.y_edge == "min":
            ymin = scene_pos.y()
        elif handle.y_edge == "max":
            ymax = scene_pos.y()

        # Enforce a minimal size on the constrained axes.
        if handle.x_edge is not None and abs(xmax - xmin) < self.MIN_SIZE:
            if handle.x_edge == "min":
                xmin = xmax - self.MIN_SIZE
            else:
                xmax = xmin + self.MIN_SIZE
        if handle.y_edge is not None and abs(ymax - ymin) < self.MIN_SIZE:
            if handle.y_edge == "min":
                ymin = ymax - self.MIN_SIZE
            else:
                ymax = ymin + self.MIN_SIZE

        self.set_bounds(xmin, ymin, xmax, ymax)
        self.rect_changed.emit(self.rect())

    def _finish_edit(self) -> None:
        self.edit_finished.emit(self.rect())
