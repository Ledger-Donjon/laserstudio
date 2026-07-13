from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from PyQt6.QtWidgets import (
    QInputDialog,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsSceneContextMenuEvent,
    QMenu,
)
from PyQt6.QtGui import QPen, QColor, QColorConstants
from PyQt6.QtCore import Qt, QPointF, QPoint
from ..instruments.probe import ProbeInstrument
from ..instruments.laser import LaserInstrument
from ..utils.colors import LedgerColors, MARKERS_COLORS
from ..utils.util import create_color_qicon
from ..utils.yaml_types import Config

if TYPE_CHECKING:
    from .stagesight import StageSight
    from .viewer import Viewer


class Marker(QGraphicsItemGroup):
    """
    Item representing a marker in a scene.
    Size can be configured depending on radius of represented object.
    """

    def __init__(
        self,
        parent: None | QGraphicsItem = None,
        viewer: None | Viewer = None,
        color: QColor | Qt.GlobalColor | int | list[float] = QColorConstants.Red,
        fillcolor: QColor
        | Qt.GlobalColor
        | int
        | list[float] = QColorConstants.Transparent,
        label: str | None = None,
    ):
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self.viewer = viewer
        if isinstance(color, list):
            color = QColor(
                int(color[0] * 255),
                int(color[1] * 255),
                int(color[2] * 255),
                int(color[3] * 255),
            )
        elif isinstance(color, Qt.GlobalColor):
            color = QColor(color)
        elif isinstance(color, int):
            color = QColor(color)

        if isinstance(fillcolor, list):
            fillcolor = QColor(
                int(fillcolor[0] * 255),
                int(fillcolor[1] * 255),
                int(fillcolor[2] * 255),
                int(fillcolor[3] * 255),
            )
        elif isinstance(fillcolor, Qt.GlobalColor):
            fillcolor = QColor(fillcolor)
        elif isinstance(fillcolor, int):
            fillcolor = QColor(fillcolor)

        self.__size: float = 10.0
        self.__color: QColor | Qt.GlobalColor | int = color
        self.__fillcolor: QColor | Qt.GlobalColor | int = fillcolor
        self.__label = label
        self._ellipse = QGraphicsEllipseItem()
        ellipse: QGraphicsEllipseItem = self._ellipse
        ellipse.setBrush(fillcolor)
        pen = self.__pen = QPen(self.__color)
        pen.setCosmetic(True)
        ellipse.setPen(pen)
        self.addToGroup(self._ellipse)
        item = self.__line1 = QGraphicsLineItem(0, 0, 0, 0)
        item.setPen(pen)
        self.addToGroup(item)
        item = self.__line2 = QGraphicsLineItem(0, 0, 0, 0)
        item.setPen(pen)
        self.addToGroup(item)
        self.__update_size()

    def __update_size(self):
        """Update the size of the items when __size is changed."""
        rad = self.__size / 2
        self._ellipse.setRect(-rad, -rad, self.__size, self.__size)
        rad = self.__size / 6
        self.__line1.setLine(-rad, rad, rad, -rad)
        self.__line2.setLine(-rad, -rad, rad, rad)

    @property
    def size(self):
        """:return: Diameter of the marker, in micrometers."""
        return self.__size

    @size.setter
    def size(self, value: float):
        """
        Set the diameter of the marker.

        :param value: New diameter, in micrometers.
        """
        if value < 0:
            raise ValueError("Size must be positive")
        self.__size = value
        self.__update_size()

    @property
    def qcolor(self) -> QColor:
        """:return: Current color, as QColor."""
        return QColor(self.__color)

    @property
    def color(self) -> QColor | Qt.GlobalColor | int:
        """:return: Current color, as QColor, Qt.GlobalColor or int."""
        return self.__color

    @color.setter
    def color(self, value: QColor | Qt.GlobalColor | int):
        """
        Set the color of the marker.

        :param value: New color, as QColor.
        """
        self.__color = value
        self.__pen.setColor(value)
        self._ellipse.setPen(self.__pen)
        self.__line1.setPen(self.__pen)
        self.__line2.setPen(self.__pen)
        self.update()

    @property
    def qfillcolor(self) -> QColor:
        """:return: Current fill color, as QColor."""
        return QColor(self.__fillcolor)

    @property
    def fillcolor(self):
        """:return: Current fill color, as QColor."""
        return self.__fillcolor

    @fillcolor.setter
    def fillcolor(self, value: QColor | Qt.GlobalColor | int):
        """
        Set the fill color of the marker.

        :param value: New fill color, as QColor.
        """
        self.__fillcolor = value
        self._ellipse.setBrush(value)

    def to_dict(self) -> Config:
        data: Config = {
            "id": self.id if isinstance(self, IdMarker) else -1,
            "pos": [self.pos().x(), self.pos().y()],
            "color": [
                self.qfillcolor.redF(),
                self.qfillcolor.greenF(),
                self.qfillcolor.blueF(),
                self.qfillcolor.alphaF(),
            ],
        }
        if not self.isVisible():
            data["hidden"] = True
        if self.label is not None:
            data["label"] = self.label
        return data

    def update_tooltip(self):
        self._ellipse.setToolTip(self.tooltip)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            logging.getLogger("laserstudio").debug(
                f"Marker item change: {change}, value: {value}"
            )
            self.update_tooltip()
        return super().itemChange(change, value)

    def set_color(self, color: QColor | Qt.GlobalColor | int):
        """Set the color of the marker."""
        self.color = color
        self.update()

    @property
    def tooltip(self) -> str:
        """The tooltip of the marker gives its position."""
        tooltip = f"Label: {self.label}\n" if self.label else ""
        tooltip += (
            "Position: ["
            + ", ".join(
                ["{:+.02f}\xa0µm".format(x) for x in (self.pos().x(), self.pos().y())]
            )
            + "]"
        )
        return tooltip

    @property
    def label(self) -> str | None:
        """The label of the marker."""
        return self.__label

    @label.setter
    def label(self, value: str | None):
        """Set the label of the marker."""
        self.__label = value
        self.update_tooltip()


class ProbeMarker(Marker):
    def __init__(self, probe: ProbeInstrument, parent: StageSight | None = None):
        super().__init__(parent)
        self.stage_sight = parent
        if self.stage_sight is not None and self.stage_sight.camera is not None:
            self.stage_sight.camera.parameter_changed.connect(
                self.__camera_parameter_changed
            )
        self.probe = probe
        probe.offset_pos_changed.connect(self.update_pos)
        probe.spot_size_changed.connect(self.update_size)
        self.color = (
            QColorConstants.Red
            if isinstance(self.probe, LaserInstrument)
            else QColorConstants.Blue
        )
        self.update_size()
        self.update_pos()

    def __camera_parameter_changed(self, parameter: str, value: Any):
        if parameter in ("objective", "resolution"):
            self.update_pos()
            self.update_size()

    def update_pos(self):
        """Update position and color."""
        if (pos := self.probe.offset_pos) is not None:
            if self.stage_sight is not None:
                if self.stage_sight.camera is not None:
                    magnification = self.stage_sight.camera.objective
                    pos = (pos[0] / magnification, pos[1] / magnification)

                self.setPos(
                    self.stage_sight.mapFromItem(self.stage_sight.image_group, *pos)
                )
            else:
                self.setPos(QPointF(*pos))
            self.setVisible(True)
        else:
            self.setVisible(False)

    def update_size(self):
        """Update the size of the marker,
        according to the spot size of the probe/spot and the current objective of the camera."""
        self.size = self.probe.spot_size_um


class IdMarker(Marker):
    """IdMarker are identifiable Markers. It is used to represent points
    added by the user and shown in the main viewer."""

    __id = 1

    def __init__(
        self,
        parent: None | QGraphicsItem = None,
        viewer: None | Viewer = None,
        color: QColor
        | Qt.GlobalColor
        | int
        | list[float]
        | LedgerColors = QColorConstants.Red,
        position: None | tuple[float, float] = None,
        label: str | None = None,
    ) -> None:
        self._id = IdMarker.__id
        IdMarker.__id += 1

        if isinstance(color, LedgerColors):
            color = color.value
        elif isinstance(color, list):
            color = QColor(
                int(color[0] * 255),
                int(color[1] * 255),
                int(color[2] * 255),
                int(color[3] * 255),
            )
        elif isinstance(color, Qt.GlobalColor):
            color = QColor(color)
        elif isinstance(color, int):
            color = QColor(color)
        super().__init__(
            parent, viewer=viewer, color=color, fillcolor=color, label=label
        )
        if position is not None:
            self.setPos(QPointF(*position))
        self.setZValue(2)
        self._label = label

    @property
    def id(self):
        """Id of the Marker, as an integer."""
        return self._id

    def set_color(self, color: QColor | Qt.GlobalColor | int):
        """Set the color of the marker."""
        self.color = color
        self.fillcolor = color
        self.update()

    @property
    def color_name(self) -> str:
        """Return HSL values as a string."""
        return "".join([f"{v:02x}" for v in self.color_hsl])

    @property
    def color_hsl(self) -> tuple[int, int, int]:
        """Return the HSL values of the color of the marker."""
        hsl = self.qfillcolor.toHsl()
        return hsl.hue(), hsl.saturation(), hsl.lightness()

    def __str__(self) -> str:
        return f"IdMarker(id={self.id}, label={self.label}, color={self.color_name})"

    def remove(self):
        """Remove the marker from the viewer or the scene."""
        if self.viewer is not None:
            self.viewer.remove_marker(self)
        else:
            if (scene := self.scene()) is not None:
                scene.removeItem(self)

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent | None) -> None:
        """Show a context menu when the marker is right-clicked."""
        menu = QMenu()
        menu.addSection(self.label)
        _ = menu.addAction("Change label...", self.set_label)
        # Submenu for setting the color of the marker
        color_menu = QMenu("Change color", menu)

        for color, name in MARKERS_COLORS:

            def on_pick(
                _checked: bool = False, *, c: QColor | Qt.GlobalColor | int = color
            ) -> None:
                self.set_color(c)

            color_menu.addAction(
                create_color_qicon(color),
                name,
                on_pick,
            )
        menu.addMenu(color_menu)
        # menu.addAction("Remove marker", self.remove)
        menu.exec(event.screenPos() if event is not None else QPoint())

    def set_label(self):
        """Set interactively the label of the marker."""
        label, ok = QInputDialog.getText(
            None, "Set label", "Enter label:", text=self.label
        )
        if ok:
            self.label = label

    @property
    def tooltip(self) -> str:
        """The tooltip of the marker gives its position and its ID."""
        tooltip = "Marker #" + (f"{self.id}") + "\n"
        return tooltip + super().tooltip
