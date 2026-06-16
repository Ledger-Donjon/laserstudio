import logging
import math
from typing import Any
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsSceneMouseEvent,
)
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QPolygonF, QPen, QPainterPath, QBrush, QColor
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection
from shapely.geometry.base import BaseGeometry
from .scanpath import ScanPath
from ..utils.scanning import ScanPathGenerator, EmptyGeometryError
from ..utils.yaml_types import Config

# Generic marker attribute (see softlimits.EDIT_HANDLE_ATTR) so the Viewer
# routes presses on these handles to the handle itself.
EDIT_HANDLE_ATTR = "is_edit_handle"
ZONE_HANDLE_SIZE = 11.0


class _ZoneVertexHandle(QGraphicsRectItem):
    """A small, constant-size square handle sitting on a zone polygon vertex.

    Dragging it moves the corresponding vertex of the (flattened) zone.
    ``ring_index`` is -1 for the exterior ring, or the interior (hole) index.
    """

    def __init__(
        self,
        owner: "ScanGeometry",
        geom_index: int,
        ring_index: int,
        vertex_index: int,
    ):
        # Not parented to the ScanGeometry group: a QGraphicsItemGroup would
        # intercept its children's mouse events (and Qt6 removed the
        # setHandlesChildEvents API to opt out). Instead the handle is added as
        # a top-level scene item so it receives its own events.
        super().__init__(
            -ZONE_HANDLE_SIZE / 2,
            -ZONE_HANDLE_SIZE / 2,
            ZONE_HANDLE_SIZE,
            ZONE_HANDLE_SIZE,
        )
        setattr(self, EDIT_HANDLE_ATTR, True)
        self._owner = owner
        self.geom_index = geom_index
        self.ring_index = ring_index
        self.vertex_index = vertex_index
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setZValue(20)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setAcceptHoverEvents(True)
        self._apply_style(hovered=False)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def _apply_style(self, hovered: bool):
        color = QColor(180, 255, 80) if hovered else QColor(100, 255, 0)
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
        self._owner._begin_vertex_edit()
        event.accept()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent | None):
        if event is None:
            return
        self._owner._move_vertex(self, event.scenePos())
        event.accept()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent | None):
        if event is None:
            return
        self._owner._end_vertex_edit()
        event.accept()


class ScanGeometry(QGraphicsItemGroup):
    def remove(self, zone: QPolygonF):
        self.__add_remove(zone, isAdd=False)

    def add(self, zone: QPolygonF):
        self.__add_remove(zone)

    def __add_remove(self, zone: QPolygonF, isAdd: bool = True):
        polygon = Polygon([(p.x(), p.y()) for p in zone])
        if not polygon.is_valid:
            return
        if polygon.is_empty:
            return
        self.scan_geometries.append((polygon, isAdd))
        self.__update()

    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent)

        self.scan_geometries: list[tuple[Polygon, bool]] = []
        self.__scan_geometry = MultiPolygon()

        # Scan geometry path item for representation
        self.__scan_geometry_items = QGraphicsItemGroup()
        self.addToGroup(self.__scan_geometry_items)
        # Scanning Path
        self.__scan_path = ScanPath(diameter=10.0)
        self.addToGroup(self.__scan_path)
        # Scan generator
        self.scan_path_generator = ScanPathGenerator()

        # Interactive vertex-edition state.
        self.__vertex_handles: list[_ZoneVertexHandle] = []
        self.__editing = False
        self.__handles_dragging = False
        self.__edit_polys: list[Polygon] = []

    def __clear_scan_geometry_items(self):
        """Clear the scan geometry items."""
        children = self.__scan_geometry_items.childItems()
        for child in children:
            child.setParentItem(None)
            del child
        children = []

    def __update_scan_geometry(self) -> list[BaseGeometry]:
        """Update the scan geometry."""
        overall_geometry = MultiPolygon()
        for polygon, add in self.scan_geometries:
            if not polygon.is_valid:
                # print("polygon is not valid")
                continue
            if add:
                # print("add", polygon)
                overall_geometry |= polygon
            else:
                # print("remove", polygon)
                overall_geometry -= polygon
        self.__scan_geometry = overall_geometry
        return (
            list(overall_geometry.geoms)
            if isinstance(overall_geometry, MultiPolygon)
            else [overall_geometry]
        )

    def __update(self):
        """
        Rebuild the scene item which displays the scanning geometry.
        """
        _geoms = self.__update_scan_geometry()

        self.__clear_scan_geometry_items()
        for geom in _geoms:
            if not isinstance(geom, Polygon):
                logging.getLogger("laserstudio").warning(
                    f"geom is not a Polygon: {geom=}, {type(geom)=}..."
                )
                continue
            if not geom.is_valid:
                logging.getLogger("laserstudio").warning(
                    f"geom is not valid: {geom=}, {geom.is_valid=}"
                )
                continue
            item = ScanGeometry.__poly_to_path_item(geom)
            self.__scan_geometry_items.addToGroup(item)

        self.scan_path_generator.geometry = self.__scan_geometry
        self.__update_scan_path()

        if not self.__editing:
            self.__rebuild_handles()

    # -- Interactive vertex edition --------------------------------------
    def __current_polygons(self) -> list[Polygon]:
        """Return the polygons of the currently displayed (merged) geometry."""
        geometry = self.__scan_geometry
        if isinstance(geometry, MultiPolygon):
            return [p for p in geometry.geoms if isinstance(p, Polygon)]
        if isinstance(geometry, Polygon):
            return [] if geometry.is_empty else [geometry]
        return []

    @staticmethod
    def __ring_coords(poly: Polygon, ring_index: int) -> list[tuple[float, float]]:
        if ring_index < 0:
            ring = poly.exterior
        else:
            interiors = list(poly.interiors)
            if ring_index >= len(interiors):
                return []
            ring = interiors[ring_index]
        # Drop the closing duplicate point.
        return [(float(x), float(y)) for x, y in list(ring.coords)[:-1]]

    def __rebuild_handles(self):
        """Recreate the vertex handles from the current geometry."""
        scene = self.scene()
        for handle in self.__vertex_handles:
            if (scene := handle.scene()) is not None:
                scene.removeItem(handle)
        self.__vertex_handles = []

        # The handles are top-level scene items; if we are not in a scene yet
        # there is nothing to attach them to.
        if scene is None:
            return

        polys = self.__edit_polys if self.__editing else self.__current_polygons()
        for geom_index, poly in enumerate(polys):
            if not isinstance(poly, Polygon) or poly.is_empty:
                continue
            rings = [-1] + list(range(len(list(poly.interiors))))
            for ring_index in rings:
                coords = self.__ring_coords(poly, ring_index)
                for vertex_index, (x, y) in enumerate(coords):
                    handle = _ZoneVertexHandle(
                        self, geom_index, ring_index, vertex_index
                    )
                    handle.setPos(QPointF(x, y))
                    handle.setVisible(False)
                    scene.addItem(handle)
                    self.__vertex_handles.append(handle)

    def __reposition_handles(self):
        """Update handle positions from the edited polygons (no recreation)."""
        for handle in self.__vertex_handles:
            if handle.geom_index >= len(self.__edit_polys):
                continue
            poly = self.__edit_polys[handle.geom_index]
            coords = self.__ring_coords(poly, handle.ring_index)
            if handle.vertex_index < len(coords):
                x, y = coords[handle.vertex_index]
                handle.setPos(QPointF(x, y))

    def update_cursor_proximity(
        self, scene_point: QPointF | None, threshold: float
    ) -> None:
        """Show a vertex handle when the cursor gets close to it."""
        if self.__handles_dragging:
            return
        for handle in self.__vertex_handles:
            if scene_point is None:
                handle.setVisible(False)
                continue
            pos = handle.pos()
            distance = math.hypot(pos.x() - scene_point.x(), pos.y() - scene_point.y())
            handle.setVisible(distance <= threshold)

    def _begin_vertex_edit(self):
        self.__handles_dragging = True
        if not self.__editing:
            self.__editing = True
            # Flatten the merged geometry into individually editable polygons.
            self.__edit_polys = self.__current_polygons()

    def _move_vertex(self, handle: _ZoneVertexHandle, scene_point: QPointF):
        if not self.__editing or handle.geom_index >= len(self.__edit_polys):
            return
        poly = self.__edit_polys[handle.geom_index]
        exterior = self.__ring_coords(poly, -1)
        interiors = [
            self.__ring_coords(poly, i) for i in range(len(list(poly.interiors)))
        ]
        point = (scene_point.x(), scene_point.y())
        if handle.ring_index < 0:
            if handle.vertex_index < len(exterior):
                exterior[handle.vertex_index] = point
        elif handle.ring_index < len(interiors):
            ring = interiors[handle.ring_index]
            if handle.vertex_index < len(ring):
                ring[handle.vertex_index] = point
        try:
            self.__edit_polys[handle.geom_index] = Polygon(exterior, interiors)
        except Exception:
            return
        self.__render_edit_polys()
        self.__reposition_handles()

    def __render_edit_polys(self):
        """Render the raw (non-merged) edited polygons during a drag."""
        self.__clear_scan_geometry_items()
        for poly in self.__edit_polys:
            if not isinstance(poly, Polygon) or poly.is_empty:
                continue
            try:
                item = ScanGeometry.__poly_to_path_item(poly)
            except Exception:
                continue
            self.__scan_geometry_items.addToGroup(item)

    def _end_vertex_edit(self):
        self.__handles_dragging = False
        if not self.__editing:
            return
        self.__editing = False
        polys = [
            p
            for p in self.__edit_polys
            if isinstance(p, Polygon) and p.is_valid and not p.is_empty
        ]
        self.scan_geometries = [(p, True) for p in polys]
        self.__edit_polys = []
        self.__update()

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
        pen = QPen(QColor(100, 255, 0))
        pen.setCosmetic(True)
        item.setPen(pen)
        brush = QBrush(QColor(0, 255, 0, 10))
        item.setBrush(brush)
        return item

    def next_point(self) -> tuple[float, float] | None:
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

    @property
    def diameter(self) -> float:
        """
        Diameter of the points in the scan path.
        """
        return self.__scan_path.diameter

    @diameter.setter
    def diameter(self, value: float):
        self.__scan_path.diameter = value
        self.__update_scan_path()

    @property
    def color(self) -> QColor:
        """Color of the scan path"""
        return self.__scan_path.color

    @color.setter
    def color(self, value: QColor):
        logging.getLogger("laserstudio").debug(f"Scan geometry color: {value.name()}")
        self.__scan_path.color = value
        self.__update_scan_path()

    @staticmethod
    def shapely_to_yaml(
        geometry: BaseGeometry | Polygon | MultiPolygon | GeometryCollection,
    ) -> dict[str, Any]:
        """
        :return: A dict for YAML serialization.
        :g: Any shapely geometry object.
        """
        if isinstance(geometry, Polygon):
            res: dict[str, list[dict[str, float]] | list[list[dict[str, float]]]] = {}
            res["exterior"] = list(
                {"x": p[0], "y": p[1]} for p in geometry.exterior.coords
            )
            interiors: list[list[dict[str, float]]] = []
            for interior in geometry.interiors:
                interiors.append(list({"x": p[0], "y": p[1]} for p in interior.coords))
            res["interiors"] = interiors
            return {"polygon": res}
        elif isinstance(geometry, MultiPolygon):
            res_multi: list[dict[str, Any]] = []
            for poly in geometry.geoms:
                res_multi.append(__class__.shapely_to_yaml(poly))
            return {"multipolygon": res_multi}
        elif isinstance(geometry, GeometryCollection):
            # We have this type when the zone is empty.
            return {"geometrycollection": None}
        else:
            # This should not happen.
            logging.getLogger("laserstudio").warning(
                f"Shapely geometry is not a Polygon, MultiPolygon, or GeometryCollection: {geometry=}, {type(geometry)=}..."
            )
            pass
        # If this line is reached, some shapely type handling may be missing.
        assert False

    @staticmethod
    def yaml_to_shapely(
        yaml: dict[str, Any],
    ) -> Polygon | MultiPolygon | GeometryCollection:
        assert len(yaml) == 1
        type_, value = next(iter(yaml.items()))
        logging.getLogger("laserstudio").debug(
            f"Scan Geometry YAML to Shapely: {type_=}, {value=}..."
        )
        if type_ == "polygon":
            exterior = list((float(p["x"]), float(p["y"])) for p in value["exterior"])
            interiors: list[list[tuple[float, float]]] = []
            for value_sub in value["interiors"]:
                interior = list((float(p["x"]), float(p["y"])) for p in value_sub)
                interiors.append(interior)
            logging.getLogger("laserstudio").debug(
                f"Scan Geometry YAML to Shapely: Polygon: {exterior=}, {interiors=}..."
            )
            polygon = Polygon(shell=exterior, holes=interiors)
            logging.getLogger("laserstudio").debug(
                f"Scan Geometry YAML to Shapely: Polygon: {polygon}..."
            )
            return polygon
        elif type_ == "multipolygon":
            multipolygon = list[Polygon]()
            for value_sub in value:
                poly = __class__.yaml_to_shapely(value_sub)
                if isinstance(poly, Polygon):
                    multipolygon.append(poly)
                elif isinstance(poly, MultiPolygon):
                    multipolygon.extend(poly.geoms)
                else:
                    logging.getLogger("laserstudio").warning(
                        f"Invalid polygon type: {type(poly)=}, {poly=}"
                    )
                    continue
            return MultiPolygon(polygons=multipolygon)
        elif type_ == "geometrycollection":
            return GeometryCollection()
        else:
            # If this line is reached, some shapely type handling may be missing.
            assert False

    @property
    def settings(self) -> Config:
        c = {}
        c["geometry"] = __class__.shapely_to_yaml(self.__scan_geometry)
        c["density"] = self.density
        return c

    @settings.setter
    def settings(self, data: Config):
        logging.getLogger("laserstudio").debug(f"Scan Geometry settings: {data}...")
        
        if "density" in data and isinstance(data["density"], int):
            self.density = data["density"]

        if "polygon" in data or "multipolygon" in data or "geometrycollection" in data:
            dictionary = data
        elif "geometry" in data and isinstance(data["geometry"], dict):
            dictionary = data["geometry"]
        else:
            logging.getLogger("laserstudio").error(
                f"Invalid data for scan geometry: {data=}"
            )
            return
        
        geoms = __class__.yaml_to_shapely(dictionary)
        if isinstance(geoms, Polygon):
            self.scan_geometries = [(geoms, True)]
        elif isinstance(geoms, MultiPolygon):
            self.scan_geometries = [(poly, True) for poly in geoms.geoms]
        else:
            logging.getLogger("laserstudio").warning(
                f"Invalid geometry type: {type(geoms)=}, {geoms=}"
            )
            return

        self.__update()
