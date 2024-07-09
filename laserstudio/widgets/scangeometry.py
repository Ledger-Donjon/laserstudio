from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsPathItem,
)
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPolygonF, QPen, QPainterPath, QBrush, QColor
import logging
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection
from typing import Optional, Union
from .scanpath import ScanPath
from ..utils.scanning import ScanPathGenerator, EmptyGeometryError


class ScanGeometry(QGraphicsItemGroup):
    def __init__(self, parent: Optional[QGraphicsItem] = None):
        super().__init__(parent)
        self.__scan_geometry = MultiPolygon()

        # Scanning Path
        self.__scan_path = ScanPath(diameter=10.0)
        self.addToGroup(self.__scan_path)
        self.__scan_zones_group = QGraphicsItemGroup()
        self.addToGroup(self.__scan_zones_group)

        # Scan generator
        self.scan_path_generator = ScanPathGenerator()

    @staticmethod
    def __poly_to_path_item(poly: Polygon) -> QGraphicsPathItem:
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

        if isinstance(self.__scan_geometry, Polygon):
            self.__scan_zones_group.addToGroup(
                ScanGeometry.__poly_to_path_item(self.__scan_geometry)
            )
        else:
            for poly in self.__scan_geometry.geoms:
                self.__scan_zones_group.addToGroup(
                    ScanGeometry.__poly_to_path_item(poly)
                )
        self.addToGroup(self.__scan_zones_group)

        # Also, update the scan path with the new geometry
        self.scan_path_generator.geometry = self.__scan_geometry
        self.__update_scan_path()

    def __update_scan_path(self):
        """Update scanning path display."""
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
        g = Polygon([(p.x(), p.y()) for p in zone])
        if isAdd:
            self.__scan_geometry |= g
        else:
            self.__scan_geometry -= g
        # In case that shapely converts it to a Polygon, we stick at a MultiPolygon
        logging.getLogger("laserstudio").debug(self.__scan_geometry)
        if isinstance(self.__scan_geometry, Polygon):
            self.__scan_geometry = MultiPolygon([self.__scan_geometry])

        # Rebuild scan zone shape in the view to display the new zone.
        self.__update()

    def remove(self, zone: QPolygonF):
        self.__add_remove(zone, isAdd=False)

    def add(self, zone: QPolygonF):
        self.__add_remove(zone)

    def next_point(self) -> Optional[tuple[float, float]]:
        if self.scan_path_generator.is_empty():
            logging.getLogger("laserstudio").error(
                "Cannot get next point, the scan geometry is empty."
            )
            return None
        try:
            self.__update_scan_path()
            next_point = self.scan_path_generator.pop()
            return next_point
        except EmptyGeometryError:
            logging.getLogger("laserstudio").error("Cannot generate a point.")

    @property
    def density(self) -> int:
        """
        Number of points generated randomly in the scan shape. The bigger it
        is, the smaller average distance between consecutive points is.
        Changing this parameter will generate a new set of points.
        """
        return self.scan_path_generator.density

    @density.setter
    def density(self, value: int):
        if value < 1:
            raise ValueError("Invalid density")
        self.scan_path_generator.density = value
        self.__update_scan_path()

    @staticmethod
    def shapely_to_yaml(
        geometry: Union[Polygon, MultiPolygon, GeometryCollection]
    ) -> dict:
        """
        :return: A dict for YAML serialization.
        :g: Any shapely geometry object.
        """
        if isinstance(geometry, Polygon):
            res = dict()
            res["exterior"] = list(
                {"x": p[0], "y": p[1]} for p in geometry.exterior.coords
            )
            interiors = []
            res["interiors"] = interiors
            for interior in geometry.interiors:
                interiors.append(list({"x": p[0], "y": p[1]} for p in interior.coords))
            return {"polygon": res}
        elif isinstance(geometry, MultiPolygon):
            res = []
            for poly in geometry.geoms:
                res.append(__class__.shapely_to_yaml(poly))
            return {"multipolygon": res}
        elif isinstance(geometry, GeometryCollection):
            # We have this type when the zone is empty.
            return {"geometrycollection": None}
        # If this line is reached, some shapely type handling may be missing.
        assert False

    @staticmethod
    def yaml_to_shapely(yaml: dict) -> Union[Polygon, MultiPolygon, GeometryCollection]:
        assert len(yaml) == 1
        type_, value = next(iter(yaml.items()))
        if type_ == "polygon":
            exterior = list((float(p["x"]), float(p["y"])) for p in value["exterior"])
            interiors = []
            for value_sub in value["interiors"]:
                interior = list((float(p["x"]), float(p["y"])) for p in value_sub)
                interiors.append(interior)
            return Polygon(shell=exterior, holes=interiors)
        elif type_ == "multipolygon":
            polys = []
            for value_sub in value:
                polys.append(__class__.yaml_to_shapely(value_sub))
            return MultiPolygon(polygons=polys)
        elif type_ == "geometrycollection":
            return GeometryCollection()
        else:
            assert False

    @property
    def yaml(self) -> dict:
        return __class__.shapely_to_yaml(self.__scan_geometry)

    @yaml.setter
    def yaml(self, dict: dict):
        self.__scan_geometry = __class__.yaml_to_shapely(dict)
        self.__update()
