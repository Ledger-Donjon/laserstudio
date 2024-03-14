from PyQt6.QtWidgets import (
    QGraphicsItemGroup,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
)
from PyQt6.QtGui import QPen, QColor, QColorConstants
from ..instruments.probe import ProbeInstrument
from ..instruments.laser import LaserInstrument
from PyQt6.QtCore import Qt, QPointF
from typing import Union, TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .stagesight import StageSight


class Marker(QGraphicsItemGroup):
    """
    Item representing the a marker in a scene.
    Size can be configured depending on radius of represented object.
    """

    def __init__(
        self,
        parent=None,
        color=QColorConstants.Red,
        fillcolor=QColorConstants.Transparent,
    ):
        super().__init__(parent)
        self.__size = 10.0
        self.__color = color
        self.__fillcolor = fillcolor
        item = self.__ellipse = QGraphicsEllipseItem()
        item.setBrush(fillcolor)
        pen = self.__pen = QPen(self.__color)
        pen.setCosmetic(True)
        item.setPen(pen)
        self.addToGroup(self.__ellipse)
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
        self.__ellipse.setRect(-rad, -rad, self.__size, self.__size)
        rad = self.__size / 6
        self.__line1.setLine(-rad, rad, rad, -rad)
        self.__line2.setLine(-rad, -rad, rad, rad)

    @property
    def size(self):
        """:return: Diameter of the laser sight, in micrometers."""
        return self.__size

    @size.setter
    def size(self, value):
        """
        Set the diameter of the laser sight.

        :param value: New diameter, in micrometers.
        """
        assert value >= 0
        self.__size = value
        self.__update_size()

    @property
    def color(self):
        """:return: Current color, as QColor."""
        return self.__color

    @color.setter
    def color(self, value: Union[QColor, Qt.GlobalColor, int]):
        """
        Set the color of the marker.

        :param value: New color, as QColor.
        """
        self.__color = value
        self.__pen.setColor(value)
        self.__ellipse.setPen(self.__pen)
        self.__line1.setPen(self.__pen)
        self.__line2.setPen(self.__pen)
        self.update()

    @property
    def fillcolor(self):
        """:return: Current fill color, as QColor."""
        return self.__fillcolor

    @fillcolor.setter
    def fillcolor(self, value: Union[QColor, Qt.GlobalColor, int]):
        """
        Set the fill color of the marker.

        :param value: New fill color, as QColor.
        """
        self.__fillcolor = value
        self.__ellipse.setBrush(value)


class ProbeMarker(Marker):
    def __init__(self, probe: ProbeInstrument, parent: Optional["StageSight"] = None):
        super().__init__(parent)
        self.stage_sight = parent
        self.probe = probe
        probe.fixed_pos_changed.connect(self.update_pos)
        self.color = (
            QColorConstants.Red
            if isinstance(self.probe, LaserInstrument)
            else QColorConstants.Blue
        )
        self.update_pos()

    def update_pos(self):
        """Update position and color."""
        if (pos := self.probe.fixed_pos) is not None:
            if self.stage_sight is not None:
                self.setPos(
                    self.stage_sight.mapFromItem(self.stage_sight.image_group, *pos)
                )
            else:
                self.setPos(QPointF(*pos))
            self.setVisible(True)
        else:
            self.setVisible(False)

    def setToolTip(self, value: str):
        self.__ellipse.setToolTip(value)
