from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
)
from PyQt6.QtGui import QPen, QColor, QColorConstants
from ..instruments.probe import ProbeInstrument
from ..instruments.laser import LaserInstrument
from PyQt6.QtCore import Qt, QPointF
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .stagesight import StageSight


class Marker(QGraphicsItemGroup):
    """
    Item representing a marker in a scene.
    Size can be configured depending on radius of represented object.
    """

    def __init__(
        self,
        parent: None | QGraphicsItem = None,
        color: QColor | Qt.GlobalColor | int | list[float] = QColorConstants.Red,
        fillcolor: QColor
        | Qt.GlobalColor
        | int
        | list[float] = QColorConstants.Transparent,
        label: str | None = None,
    ):
        super().__init__(parent)
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
        self.__color = color
        self.__fillcolor = fillcolor
        self.label = label
        item = self._ellipse = QGraphicsEllipseItem()
        item.setBrush(fillcolor)
        pen = self.__pen = QPen(self.__color)
        pen.setCosmetic(True)
        item.setPen(pen)
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

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id if isinstance(self, IdMarker) else -1,
            "pos": [self.pos().x(), self.pos().y()],
            "color": [
                self.qfillcolor.redF(),
                self.qfillcolor.greenF(),
                self.qfillcolor.blueF(),
                self.qfillcolor.alphaF(),
            ],
        }
        if self.label is not None:
            data["label"] = self.label
        return data


class ProbeMarker(Marker):
    def __init__(self, probe: ProbeInstrument, parent: Optional["StageSight"] = None):
        super().__init__(parent)
        self.stage_sight = parent
        self.probe = probe
        probe.offset_pos_changed.connect(self.update_pos)  # type: ignore
        self.color = (
            QColorConstants.Red
            if isinstance(self.probe, LaserInstrument)
            else QColorConstants.Blue
        )
        self.update_pos()

    def update_pos(self):
        """Update position and color."""
        if (pos := self.probe.offset_pos) is not None:
            if self.stage_sight is not None:
                self.setPos(
                    self.stage_sight.mapFromItem(self.stage_sight.image_group, *pos)
                )
            else:
                self.setPos(QPointF(*pos))
            self.setVisible(True)
        else:
            self.setVisible(False)

    def setToolTip(self, toolTip: str | None):
        self._ellipse.setToolTip(toolTip)


class IdMarker(Marker):
    """IdMarker are identifiable Markers. It is used to represent points
    added by the user and shown in the main viewer."""

    __id = 1

    def __init__(
        self,
        parent: None | QGraphicsItem = None,
        color: QColor | Qt.GlobalColor | int | list[float] = QColorConstants.Red,
        label: str | None = None,
    ) -> None:
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
        super().__init__(parent, color=color, fillcolor=color, label=label)
        self._id = IdMarker.__id
        IdMarker.__id += 1

    @property
    def id(self):
        """Id of the Marker, as an integer."""
        return self._id

    def update_tooltip(self):
        """The tooltip of the marker gives its position and its ID."""
        label = f"M{self.id}" if self.label is None else self.label
        self.setToolTip(
            f"{label}: "
            + ", ".join(["{:.2f}".format(x) for x in (self.pos().x(), self.pos().y())])
        )
