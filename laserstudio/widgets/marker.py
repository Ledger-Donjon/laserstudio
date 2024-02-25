from PyQt6.QtWidgets import (
    QGraphicsItemGroup,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
)
from PyQt6.QtGui import QPen, QColor


class Marker(QGraphicsItemGroup):
    """
    Item representing the a marker in the scene.
    Size can be configured depending on radius of represented object.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.__size = 10.0
        self.__color = QColor(255, 0, 0)
        item = self.__ellipse = QGraphicsEllipseItem()
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
    def color(self, value):
        """
        Set the color of the laser sight.
        :param value: New color, as QColor.
        """
        assert isinstance(value, QColor)
        self.__color = value
        self.__pen.setColor(value)
        self.__ellipse.setPen(self.__pen)
        self.__line1.setPen(self.__pen)
        self.__line2.setPen(self.__pen)
