from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsPathItem,
)
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPolygonF, QPen, QPainterPath, QBrush, QColor
import logging
import shapely.geometry as geo
from typing import Optional
from .scanpath import ScanPath
from ..scanning import ScanPathGenerator, EmptyGeometryError


class ScanGeometry(QGraphicsItemGroup):
    def __init__(self, parent: Optional[QGraphicsItem] = None):
        super().__init__(parent)
        self.__scan_geometry = geo.MultiPolygon()

        # Scanning Path
        self.__scan_path = ScanPath(diameter=10.0)
        self.addToGroup(self.__scan_path)
        self.__scan_zones_group = QGraphicsItemGroup()
        self.addToGroup(self.__scan_zones_group)

        # Scan generator
        self.scan_path_generator = ScanPathGenerator()

    @staticmethod
    def __poly_to_path_item(poly: geo.Polygon) -> QGraphicsPathItem:
        """
        Create a QGraphicsPathItem according to Polygon.

        Note: don't use QGraphicsPolygonItems which will display lines from
            outer ring to inner rings. Prefer usage of QGraphicsPathItem which has
            much better display for polygons with holes.

        :param poly: The Shapely Polygon to convert to Graphics Path Item
        :return: A Graphics path item
        """
        # Get the exterior of the Polygon
        coords_ext = list(poly.exterior.coords)
        qPoly = QPolygonF([QPointF(*p) for p in coords_ext])
        path = QPainterPath()
        path.addPolygon(qPoly)

        # Treat the holes
        for interior in poly.interiors:
            coords_int = list(interior.coords)
            qPoly = QPolygonF([QPointF(*p) for p in coords_int])
            path2 = QPainterPath()
            path2.addPolygon(qPoly)
            path = path.subtracted(path2)
        item = QGraphicsPathItem(path)
        item.setPen(QPen(QColor(100, 255, 0), 0))
        item.setBrush(QBrush(QColor(0, 255, 0, 10)))
        return item

    def __update(self):
        """
        Rebuild the scene item which displays the scanning geometry. This will
        create a Qt item from a shapely geometry polygon.
        """
        # Remove previous display if defined
        children = self.__scan_zones_group.childItems()
        for child in children:
            child.setParentItem(None)
            del child
        children = []

        for poly in self.__scan_geometry.geoms:
            self.__scan_zones_group.addToGroup(ScanGeometry.__poly_to_path_item(poly))
        self.addToGroup(self.__scan_zones_group)

        # Also, update the scan path with the new geometry
        self.__update_scan_path()

    def __update_scan_path(self):
        """Update scanning path display."""

        self.scan_path_generator.geometry = self.__scan_geometry

        try:
            points_hist = self.scan_path_generator.hist_list(10)
            points_next = self.scan_path_generator.next_list(10)
        except EmptyGeometryError:
            points_hist = []
            points_next = []
        qPoints = [QPointF(*p) for p in points_hist + points_next]
        self.__scan_path.set(qPoints, len(points_hist), self.__scan_path.diameter)

    def __add_remove(self, zone: QPolygonF, isAdd: bool = True):
        # Converts the Polygon to a shapely instance.
        g = geo.Polygon([(p.x(), p.y()) for p in zone])
        if isAdd:
            self.__scan_geometry |= g
        else:
            self.__scan_geometry -= g
        # In case that shapely converts it to a Polygon, we stick at a MultiPolygon
        logging.debug(self.__scan_geometry)
        if isinstance(self.__scan_geometry, geo.Polygon):
            self.__scan_geometry = geo.MultiPolygon([self.__scan_geometry])

        # Rebuild scan zone shape in the view to display the new zone.
        self.__update()

    def remove(self, zone: QPolygonF):
        self.__add_remove(zone, isAdd=False)

    def add(self, zone: QPolygonF):
        self.__add_remove(zone)
