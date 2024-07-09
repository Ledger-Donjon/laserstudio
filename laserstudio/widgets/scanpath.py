from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QGraphicsItemGroup, QGraphicsEllipseItem, QGraphicsPathItem
from PyQt6.QtGui import QPen, QColor, QPainterPath, QColorConstants


class ScanPath(QGraphicsItemGroup):
    """Represents the scanning path"""

    def __init__(self, diameter: float = 0.0, hist_size: int = 0):
        super().__init__()
        self.__path: list[QPointF] = []
        self.__diameter = diameter
        self.__hist_size = hist_size

    @property
    def path(self) -> list[QPointF]:
        """list of points in the path"""
        # Clone the list to prevent external modification
        return self.__path

    @path.setter
    def path(self, value: list[QPointF]):
        self.__path = value
        self.__rebuild()

    @property
    def diameter(self) -> float:
        """Diameter of the points"""
        return self.__diameter

    @diameter.setter
    def diameter(self, value: float):
        self.__diameter = value
        self.__rebuild()

    @property
    def hist_size(self) -> int:
        """
        Number of historical points in the path.
        Historical points are represented differently.
        """
        return self.__hist_size

    @hist_size.setter
    def hist_size(self, value: int):
        self.__hist_size = value
        self.__rebuild()

    def set(self, path: list[QPointF], hist_size: int, diameter: float):
        """Sets all attributes and rebuild the graphic object at once."""
        self.__hist_size = hist_size
        self.__diameter = diameter
        self.path = path

    def __rebuild(self):
        """Recreate the graphic items to represent the path"""
        for i in self.childItems():
            i.setParentItem(None)

        red = QColorConstants.Red
        red_t = QColor(red)
        red_t.setAlpha(100)

        # Add circles for all points in the path.
        for i, point in enumerate(self.__path):
            radius = self.__diameter / 2
            item = QGraphicsEllipseItem(-radius, -radius, radius * 2, radius * 2)
            item.setPos(point)
            # Change the color for all next points
            pen = QPen(red_t if i >= self.__hist_size else red)
            pen.setCosmetic(True)
            item.setPen(pen)
            self.addToGroup(item)

        # Add a path to show scanning order
        # We want the path to have two different colors, so we must draw two
        # paths.
        painter_path = QPainterPath()
        for i, point in enumerate(self.__path[: self.__hist_size + 1]):
            if i == 0:
                painter_path.moveTo(point)
            else:
                painter_path.lineTo(point)
        item = QGraphicsPathItem(painter_path)
        pen = QPen(red)
        pen.setCosmetic(True)
        item.setPen(pen)
        self.addToGroup(item)

        # Second path for next points
        painter_path = QPainterPath()
        for i, point in enumerate(self.__path[self.__hist_size :]):
            if i == 0:
                painter_path.moveTo(point)
            else:
                painter_path.lineTo(point)
        item = QGraphicsPathItem(painter_path)
        pen = QPen(red_t)
        pen.setCosmetic(True)
        item.setPen(pen)
        self.addToGroup(item)
