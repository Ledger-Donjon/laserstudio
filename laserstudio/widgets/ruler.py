from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QTransform,
)
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsRectItem,
    QGraphicsSceneContextMenuEvent,
    QGraphicsSceneMouseEvent,
    QGraphicsSimpleTextItem,
    QInputDialog,
    QMenu,
    QStyleOptionGraphicsItem,
    QWidget,
)

from ..utils.colors import LedgerColors, MARKERS_COLORS
from ..utils.util import create_color_qicon
from ..utils.yaml_types import Config
from .softlimits import EDIT_HANDLE_ATTR

if TYPE_CHECKING:
    from .viewer import Viewer


def format_length(um: float) -> str:
    """Format a length, in micrometers, switching to millimeters above 1000 µm."""
    if abs(um) >= 1000.0:
        return f"{um / 1000.0:.03f}\xa0mm"
    return f"{um:.02f}\xa0µm"


def _to_qcolor(
    color: QColor | Qt.GlobalColor | int | list[float] | LedgerColors,
) -> QColor:
    """Normalize the color representations accepted by the API into a QColor."""
    if isinstance(color, LedgerColors):
        return QColor(color.value)
    if isinstance(color, list):
        return QColor(
            int(color[0] * 255),
            int(color[1] * 255),
            int(color[2] * 255),
            int(color[3] * 255) if len(color) > 3 else 255,
        )
    return QColor(color)


class _EndpointHandle(QGraphicsRectItem):
    """Constant-size square handle used to move one end of a ruler.

    The handle index (0 or 1) selects which endpoint the drag moves.
    """

    SIZE = 10.0

    def __init__(self, owner: "Ruler", index: int):
        super().__init__(-self.SIZE / 2, -self.SIZE / 2, self.SIZE, self.SIZE, owner)
        setattr(self, EDIT_HANDLE_ATTR, True)
        self._owner = owner
        self.index = index
        # Keep the handle at a constant pixel size whatever the view zoom.
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setZValue(1)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        # Revealed by Ruler.update_cursor_proximity when the cursor comes close.
        self.setVisible(False)
        self.apply_style(hovered=False)

    def apply_style(self, hovered: bool):
        color = self._owner.qcolor
        pen = QPen(QColor(255, 255, 255))
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QBrush(color if hovered else color.lighter(115)))

    def hoverEnterEvent(self, event):
        self.apply_style(hovered=True)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.apply_style(hovered=False)
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
        self._owner.set_endpoint(self.index, event.scenePos())
        event.accept()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent | None):
        if event is None:
            return
        self._owner._dragging = False
        event.accept()


class Ruler(QGraphicsObject):
    """
    Measurement annotation: a straight segment between two scene points, showing
    its length, an optional label, and optional graduations at a fixed interval.

    Like the markers, rulers are identified by an integer id, are owned by the
    :class:`~laserstudio.widgets.viewer.Viewer` and are serialized to the
    settings file.
    """

    # Emitted whenever something shown in the view or in the rulers list changed
    # (geometry, color, label or graduation).
    changed = pyqtSignal()

    # Constant on-screen sizes, in pixels.
    END_CAP_PX = 7.0
    TICK_PX = 4.0
    MAJOR_TICK_PX = 7.0
    HIT_WIDTH_PX = 8.0
    LABEL_OFFSET_PX = 9.0
    # Graduations closer than this on screen are an unreadable smear, so they are
    # not drawn at all.
    MIN_TICK_SPACING_PX = 4.0
    # A ruler may extend far outside the viewport, where the spacing rule above
    # no longer bounds the work: a metre-long ruler graduated every 4 µm would be
    # 250000 ticks. The cap is set well above what a readable on-screen ruler can
    # reach (with the minimal spacing, this is already 8000 px of ruler) so it
    # only ever kicks in for such extreme cases.
    MAX_TICKS = 2000

    __id = 1

    def __init__(
        self,
        p1: QPointF | tuple[float, float],
        p2: QPointF | tuple[float, float],
        parent: QGraphicsItem | None = None,
        viewer: "Viewer | None" = None,
        color: QColor
        | Qt.GlobalColor
        | int
        | list[float]
        | LedgerColors = LedgerColors.Grellow,
        label: str | None = None,
        graduation: float | None = None,
        graduation_count: float | None = None,
    ):
        super().__init__(parent)
        self._id = Ruler.__id
        Ruler.__id += 1

        self.viewer = viewer
        self._p1 = QPointF(*p1) if isinstance(p1, tuple) else QPointF(p1)
        self._p2 = QPointF(*p2) if isinstance(p2, tuple) else QPointF(p2)
        self._color = _to_qcolor(color)
        self._label = label
        # Only one graduation form is ever stored; an explicit interval wins.
        self._graduation = graduation if graduation else None
        self._graduation_count = None
        if self._graduation is None and graduation_count and graduation_count > 0:
            self._graduation_count = float(graduation_count)
        # Scene units per pixel, refreshed at each paint. Used to keep the
        # clickable area constant on screen.
        self._px = 1.0
        self._dragging = False
        self._handles_shown = False

        self.setZValue(8)
        self.setAcceptedMouseButtons(Qt.MouseButton.RightButton)

        self._text = QGraphicsSimpleTextItem(self)
        self._text.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True
        )
        self._text.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        self._handles = [_EndpointHandle(self, 0), _EndpointHandle(self, 1)]
        self._refresh()

    @property
    def id(self) -> int:
        """Id of the Ruler, as an integer."""
        return self._id

    def __str__(self) -> str:
        return f"Ruler(id={self.id}, label={self.label}, length={self.length})"

    # -- Geometry ---------------------------------------------------------
    @property
    def length(self) -> float:
        """Length of the ruler, in micrometers."""
        return math.hypot(self._p2.x() - self._p1.x(), self._p2.y() - self._p1.y())

    @property
    def midpoint(self) -> QPointF:
        return (self._p1 + self._p2) / 2.0

    def set_endpoint(self, index: int, point: QPointF) -> None:
        """Move one endpoint (0 or 1) to the given scene position."""
        self.prepareGeometryChange()
        if index == 0:
            self._p1 = QPointF(point)
        else:
            self._p2 = QPointF(point)
        self._refresh()

    # -- Appearance -------------------------------------------------------
    @property
    def qcolor(self) -> QColor:
        """:return: Current color, as QColor."""
        return QColor(self._color)

    def set_color(
        self, color: QColor | Qt.GlobalColor | int | list[float] | LedgerColors
    ) -> None:
        """Set the color of the ruler."""
        self._color = _to_qcolor(color)
        self._refresh()

    @property
    def label(self) -> str | None:
        """The label of the ruler."""
        return self._label

    @label.setter
    def label(self, value: str | None):
        """Set the label of the ruler."""
        self._label = value or None
        self._refresh()

    @property
    def graduation(self) -> float | None:
        """Graduation interval in micrometers, when set as an interval.

        None when the ruler is plain *or* graduated by count: the two forms are
        mutually exclusive. :attr:`effective_graduation` gives the interval
        actually drawn in both cases.
        """
        return self._graduation

    @graduation.setter
    def graduation(self, value: float | None):
        """Graduate at a fixed interval; 0 or None draws a plain line."""
        self._graduation = value if value and value > 0 else None
        self._graduation_count = None
        self._refresh()

    @property
    def graduation_count(self) -> float | None:
        """Number of graduations, when set as a count; None otherwise.

        Fractional counts are allowed: 7.5 graduations over a 150 µm ruler is an
        interval of 20 µm, the last graduation falling beyond the second end.
        """
        return self._graduation_count

    @graduation_count.setter
    def graduation_count(self, value: float | None):
        """Graduate in a fixed number of divisions; 0 or None draws a plain line.

        The count is kept as such, so moving an endpoint afterwards keeps the
        number of graduations and changes the interval between them.
        """
        self._graduation_count = float(value) if value and value > 0 else None
        self._graduation = None
        self._refresh()

    @property
    def effective_graduation(self) -> float | None:
        """Interval actually drawn between two ticks, whichever form is set.

        In count mode it follows the length, so it changes when an endpoint
        moves. None when the ruler is plain.
        """
        if self._graduation is not None:
            return self._graduation
        if self._graduation_count:
            length = self.length
            return length / self._graduation_count if length > 0 else None
        return None

    @property
    def effective_graduation_count(self) -> float | None:
        """Number of graduations actually drawn, whichever form is set.

        In interval mode it follows the length, so it changes when an endpoint
        moves. None when the ruler is plain.
        """
        if self._graduation_count is not None:
            return self._graduation_count
        if self._graduation:
            return self.length / self._graduation
        return None

    @property
    def text(self) -> str:
        """Text shown next to the ruler: its label, if any, and its length."""
        length = format_length(self.length)
        return f"{self._label} · {length}" if self._label else length

    @property
    def tooltip(self) -> str:
        """The tooltip of the ruler gives its id, label, length and graduation."""
        tooltip = f"Ruler #{self.id}\n"
        if self._label:
            tooltip += f"Label: {self._label}\n"
        tooltip += f"Length: {format_length(self.length)}"
        interval = self.effective_graduation
        if interval is not None:
            tooltip += f"\nGraduation: {format_length(interval)}"
            if self._graduation_count:
                tooltip += f" ({self._graduation_count:.02f} graduations)"
        return tooltip

    def _refresh(self) -> None:
        """Update the items derived from the geometry and repaint."""
        self._text.setText(self.text)
        self._text.setBrush(QBrush(self._color))
        self._text.setPos(self.midpoint)
        # The text ignores the view transform, so its own transform is applied
        # in device pixels: center it above the middle of the segment.
        rect = self._text.boundingRect()
        transform = QTransform()
        transform.translate(-rect.width() / 2, -rect.height() - self.LABEL_OFFSET_PX)
        self._text.setTransform(transform)

        for handle in self._handles:
            handle.setPos(self._p1 if handle.index == 0 else self._p2)
            handle.apply_style(hovered=False)

        self.setToolTip(self.tooltip)
        self.update()
        self.changed.emit()

    # -- Painting ---------------------------------------------------------
    def boundingRect(self) -> QRectF:
        margin = _EndpointHandle.SIZE + self.MAJOR_TICK_PX
        rect = QRectF(self._p1, self._p2).normalized()
        return rect.adjusted(-margin, -margin, margin, margin)

    def shape(self) -> QPainterPath:
        # Only the segment itself is clickable, so a ruler does not shadow the
        # items underneath it (edit handles, stage moves) with a filled
        # bounding box.
        path = QPainterPath(self._p1)
        path.lineTo(self._p2)
        stroker = QPainterPathStroker()
        stroker.setWidth(max(self.HIT_WIDTH_PX * self._px, 1e-9))
        return stroker.createStroke(path)

    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = None,
    ) -> None:
        if painter is None:
            return
        transform = painter.worldTransform()
        scale = math.hypot(transform.m11(), transform.m12())
        # Scene units for one pixel on screen, used for every constant-size
        # decoration (end caps, graduations, clickable area).
        self._px = 1.0 / scale if scale > 0 else 1.0

        pen = QPen(self._color)
        pen.setCosmetic(True)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(self._p1, self._p2)

        length = self.length
        if length <= 0:
            return
        # Unit vector along the ruler, and the perpendicular the ticks follow.
        direction = (self._p2 - self._p1) / length
        normal = QPointF(-direction.y(), direction.x())

        self._draw_tick(painter, self._p1, normal, self.END_CAP_PX)
        self._draw_tick(painter, self._p2, normal, self.END_CAP_PX)
        self._draw_graduations(painter, length, direction, normal)

    def _draw_tick(
        self,
        painter: QPainter,
        center: QPointF,
        normal: QPointF,
        half_length_px: float,
    ) -> None:
        """Draw one tick across the ruler, of a constant length on screen."""
        offset = normal * (half_length_px * self._px)
        painter.drawLine(center - offset, center + offset)

    def _draw_graduations(
        self,
        painter: QPainter,
        length: float,
        direction: QPointF,
        normal: QPointF,
    ) -> None:
        interval = self.effective_graduation
        if interval is None:
            return
        if interval / self._px < self.MIN_TICK_SPACING_PX:
            return
        count = int(length / interval)
        if count > self.MAX_TICKS:
            return
        for i in range(1, count + 1):
            # Every fifth graduation is longer, so ticks can be counted.
            half = self.MAJOR_TICK_PX if i % 5 == 0 else self.TICK_PX
            center = self._p1 + direction * (i * interval)
            self._draw_tick(painter, center, normal, half)

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
        """Show the endpoint handles when the cursor is close to an endpoint."""
        if self._dragging:
            return
        if scene_point is None or not self.isVisible():
            self._set_handles_shown(False)
            return
        near = any(
            math.hypot(scene_point.x() - p.x(), scene_point.y() - p.y()) <= threshold
            for p in (self._p1, self._p2)
        )
        self._set_handles_shown(near)

    # -- Actions ----------------------------------------------------------
    def remove(self) -> None:
        """Remove the ruler from the viewer, or from the scene."""
        if self.viewer is not None:
            self.viewer.remove_ruler(self)
        elif (scene := self.scene()) is not None:
            scene.removeItem(self)

    def edit_label(self, parent: QWidget | None = None) -> None:
        """Set interactively the label of the ruler."""
        label, ok = QInputDialog.getText(
            parent, "Set label", "Enter label:", text=self._label or ""
        )
        if ok:
            self.label = label

    def edit_graduation(self, parent: QWidget | None = None) -> None:
        """Set interactively the graduation interval of the ruler."""
        value, ok = QInputDialog.getDouble(
            parent,
            "Set graduation",
            "Graduation interval (µm, 0 to disable):",
            self._graduation or 0.0,
            0.0,
            1e6,
            2,
        )
        if ok:
            self.graduation = value

    def edit_graduation_count(self, parent: QWidget | None = None) -> None:
        """Set interactively the number of graduations of the ruler."""
        # Coming from interval mode, start from the count it amounts to.
        current = self.effective_graduation_count
        count, ok = QInputDialog.getDouble(
            parent,
            "Set graduations",
            "Number of graduations (0 to disable):",
            current or 10.0,
            0.0,
            float(self.MAX_TICKS),
            2,
        )
        if ok:
            self.graduation_count = count

    def fill_menu(self, menu: QMenu, parent: QWidget | None = None) -> None:
        """Add the per-ruler actions to *menu*, for the viewer and the list."""
        _ = menu.addAction("Change label...", lambda: self.edit_label(parent))
        color_menu = QMenu("Change color", menu)
        for color, name in MARKERS_COLORS:

            def on_pick(
                _checked: bool = False, *, c: QColor | Qt.GlobalColor | int = color
            ) -> None:
                self.set_color(c)

            color_menu.addAction(create_color_qicon(color), name, on_pick)
        menu.addMenu(color_menu)
        _ = menu.addAction("Set graduation...", lambda: self.edit_graduation(parent))
        _ = menu.addAction(
            "Set number of graduations...",
            lambda: self.edit_graduation_count(parent),
        )
        menu.addSeparator()
        _ = menu.addAction("Remove ruler", self.remove)

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent | None) -> None:
        """Show a context menu when the ruler is right-clicked."""
        if event is None:
            return
        menu = QMenu()
        menu.addSection(f"Ruler #{self.id}")
        self.fill_menu(menu)
        menu.exec(event.screenPos())
        event.accept()

    # -- Serialization ----------------------------------------------------
    def to_dict(self) -> Config:
        data: Config = {
            "id": self.id,
            "p1": [self._p1.x(), self._p1.y()],
            "p2": [self._p2.x(), self._p2.y()],
            "length": self.length,
            "color": [
                self._color.redF(),
                self._color.greenF(),
                self._color.blueF(),
                self._color.alphaF(),
            ],
        }
        if not self.isVisible():
            data["hidden"] = True
        if self._label is not None:
            data["label"] = self._label
        if self._graduation is not None:
            data["graduation"] = self._graduation
        if self._graduation_count is not None:
            data["graduation_count"] = self._graduation_count
        return data
