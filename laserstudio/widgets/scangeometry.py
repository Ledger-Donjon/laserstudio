from __future__ import annotations

import logging
import math

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsSceneMouseEvent,
)
from shapely.geometry import Polygon

from ..utils.scanzones import ScanZone
from ..instruments.scans import ScansInstrument
from .scanpath import ScanPath

# Generic marker attribute (see softlimits.EDIT_HANDLE_ATTR) so the Viewer
# routes presses on these handles to the handle itself.
EDIT_HANDLE_ATTR = "is_edit_handle"
ZONE_HANDLE_SIZE = 11.0


class _ZoneVertexHandle(QGraphicsRectItem):
    """A small, constant-size square handle sitting on a zone polygon vertex.

    Dragging it moves the corresponding vertex of the zone it belongs to.
    ``zone_index`` identifies the zone, ``geom_index`` the polygon within that
    zone, and ``ring_index`` is -1 for the exterior ring or the interior (hole)
    index.
    """

    def __init__(
        self,
        owner: ScanGeometry,
        zone_id: int,
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
        self.zone_id = zone_id
        self.geom_index = geom_index
        self.ring_index = ring_index
        self.vertex_index = vertex_index
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setZValue(20)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setAcceptHoverEvents(True)
        self._color = QColor(100, 255, 0)
        self._apply_style(hovered=False)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def set_color(self, color: QColor):
        """Tint the handle with its zone's color."""
        self._color = QColor(color)
        self._apply_style(hovered=False)

    def _apply_style(self, hovered: bool):
        color = self._color.lighter(140) if hovered else self._color
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
        self._owner._begin_vertex_edit(self)
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


def _poly_to_path_item(
    poly: Polygon, color: QColor, *, filled: bool, active: bool
) -> QGraphicsPathItem:
    """
    Create a QGraphicsPathItem according to Polygon.

    Note: don't use QGraphicsPolygonItems which will display lines from
        outer ring to inner rings. Prefer usage of QGraphicsPathItem which has
        much better display for polygons with holes.

    :param poly: The Shapely Polygon to convert to Graphics Path Item
    :param color: The owning zone's color
    :param filled: False draws a dashed outline with no fill (disabled zone)
    :param active: True thickens the outline (the zone being drawn into)
    :return: A Graphics path item
    """
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
    pen = QPen(QColor(color))
    pen.setCosmetic(True)
    pen.setWidth(2 if active else 1)
    if not filled:
        pen.setStyle(Qt.PenStyle.DashLine)
    item.setPen(pen)
    if filled:
        fill = QColor(color)
        fill.setAlpha(10)
        item.setBrush(QBrush(fill))
    else:
        item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
    return item


class ScanGeometry(QGraphicsItemGroup):
    """Scene representation of a :class:`ScanZones` model.

    Draws one path item per rendered zone in that zone's color, plus the scan
    path, and owns the interactive vertex handles. Holds no geometry of its
    own: several instances (one per viewer) can render the same model.

    Rendering rules: an enabled zone gets a solid outline and a translucent
    fill; a disabled zone is not drawn *unless* it is the active zone, in which
    case it appears as a dashed outline with no fill so that drawing into it is
    still visible. The active zone's outline is thicker.
    """

    def __init__(self, zones: ScansInstrument, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self.zones = zones

        # Scan geometry path items for representation
        self.__scan_geometry_items = QGraphicsItemGroup()
        self.addToGroup(self.__scan_geometry_items)
        # Scanning Path
        self.__scan_path = ScanPath(diameter=zones.point_diameter)
        self.addToGroup(self.__scan_path)

        # Interactive vertex-edition state.
        self.__vertex_handles: list[_ZoneVertexHandle] = []
        self.__handles_dragging = False
        self.__editing_zone: ScanZone | None = None

        zones.zone_changed.connect(self.__on_zones_changed)
        zones.path_changed.connect(self.__update_scan_path)
        self.__on_zones_changed(-1)

    # -- Drawing gestures (called by the Viewer) ---------------------------- #

    def add(self, zone: QPolygonF):
        """Union a scene polygon into the active zone."""
        polygon = self.__to_shapely(zone)
        if polygon is not None:
            self.zones.add(polygon)

    def remove(self, zone: QPolygonF):
        """Subtract a scene polygon from the active zone."""
        polygon = self.__to_shapely(zone)
        if polygon is not None:
            self.zones.remove(polygon)

    @staticmethod
    def __to_shapely(zone: QPolygonF) -> Polygon | None:
        polygon = Polygon([(p.x(), p.y()) for p in zone])
        if polygon.is_empty or not polygon.is_valid:
            return None
        return polygon

    # -- Model-driven rendering --------------------------------------------- #

    def __rendered_zones(self) -> list[ScanZone]:
        """Return every zone that gets drawn (eg. enabled or active)."""
        return [
            zone
            for zone in self.zones.zones.values()
            if (zone.enabled or zone == self.zones.active_zone)
        ]

    def __clear_scan_geometry_items(self):
        """Clear the scan geometry items."""
        for child in self.__scan_geometry_items.childItems():
            child.setParentItem(None)
            del child

    def __on_zones_changed(self, zone_id: int):
        """Rebuild all scene items from the model."""
        self.__clear_scan_geometry_items()
        for zone in self.__rendered_zones():
            is_active = self.zones.active_zone == zone
            for poly in zone.polygons:
                if not poly.is_valid:
                    logging.getLogger("laserstudio").warning(
                        f"zone polygon is not valid: {poly=}"
                    )
                    continue
                item = _poly_to_path_item(
                    poly, zone.color, filled=zone.enabled, active=is_active
                )
                self.__scan_geometry_items.addToGroup(item)

        self.__scan_path.color = self.zones.path_color
        self.__scan_path.diameter = self.zones.point_diameter
        self.__update_scan_path()

        if self.__editing_zone is None:
            self.__rebuild_handles()

    def __update_scan_path(self):
        """Update scanning path display."""
        generator = self.zones.scan_path_generator
        if generator.is_empty():
            points_hist: list[tuple[float, float]] = []
            points_next: list[tuple[float, float]] = []
        else:
            points_hist = generator.hist_list(10)
            points_next = generator.next_list(10)
        qPoints = [QPointF(*p) for p in points_hist + points_next]
        self.__scan_path.set(qPoints, len(points_hist), self.__scan_path.diameter)

    # -- Delegating properties (kept for the classic toolbar) --------------- #

    @property
    def scan_path_generator(self):
        """The shared scan path generator."""
        return self.zones.scan_path_generator

    @property
    def density(self) -> int:
        """Number of points generated randomly in the scan shape."""
        return self.zones.density

    @density.setter
    def density(self, value: int):
        self.zones.density = value

    @property
    def diameter(self) -> float:
        """Diameter of the points in the scan path."""
        return self.zones.point_diameter

    @diameter.setter
    def diameter(self, value: float):
        self.zones.point_diameter = value

    @property
    def color(self) -> QColor:
        """Color of the scan path"""
        return self.zones.path_color

    @color.setter
    def color(self, value: QColor):
        logging.getLogger("laserstudio").debug(f"Scan path color: {value.name()}")
        self.zones.path_color = value

    def next_point(self) -> tuple[float, float] | None:
        """Pop the next scan point from the shared model."""
        return self.zones.next_point()

    # -- Interactive vertex edition ----------------------------------------- #

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
        """Recreate the vertex handles from the model."""
        scene = self.scene()
        for handle in self.__vertex_handles:
            handle_scene = handle.scene()
            if handle_scene is not None:
                handle_scene.removeItem(handle)
        self.__vertex_handles = []

        # The handles are top-level scene items; if we are not in a scene yet
        # there is nothing to attach them to.
        if scene is None:
            return

        for zone in self.__rendered_zones():
            for geom_index, poly in enumerate(zone.polygons):
                if not poly.is_valid:
                    continue
                rings = [-1] + list(range(len(list(poly.interiors))))
                for ring_index in rings:
                    for vertex_index, (x, y) in enumerate(
                        self.__ring_coords(poly, ring_index)
                    ):
                        handle = _ZoneVertexHandle(
                            self, zone.id, geom_index, ring_index, vertex_index
                        )
                        handle.set_color(zone.color)
                        handle.setPos(QPointF(x, y))
                        handle.setVisible(False)
                        scene.addItem(handle)
                        self.__vertex_handles.append(handle)

    def __reposition_handles(self):
        """Update handle positions from the edited zone (no recreation)."""
        if self.__editing_zone is None:
            return
        for handle in self.__vertex_handles:
            if handle.zone_id != self.__editing_zone.id:
                logging.getLogger("laserstudio").debug(
                    f"handle {handle.zone_id} is not the editing zone"
                )
                continue
            if handle.geom_index >= len(self.__editing_zone.polygons):
                logging.getLogger("laserstudio").debug(
                    f"handle {handle.zone_id} {handle.geom_index} is out of range"
                )
                continue
            poly = self.__editing_zone.polygons[handle.geom_index]
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

    def _begin_vertex_edit(self, handle: _ZoneVertexHandle):
        self.__handles_dragging = True
        try:
            logging.getLogger("laserstudio").debug(
                f"begin vertex edit for zone {handle.zone_id}"
            )
            self.__editing_zone = self.zones.zone(handle.zone_id)
        except KeyError:
            logging.getLogger("laserstudio").debug(f"zone {handle.zone_id} not found")
            self.__editing_zone = None
            return

        # Keep the pre-drag polygons so a drag that ends up invalid can
        self.__pre_polygons = self.__editing_zone.polygons

    def _move_vertex(self, handle: _ZoneVertexHandle, scene_point: QPointF):
        if self.__editing_zone is None or handle.zone_id != self.__editing_zone.id:
            logging.getLogger("laserstudio").debug(
                f"move vertex for zone {handle.zone_id} is not the editing zone"
            )
            return
        if handle.geom_index >= len(self.__editing_zone.polygons):
            logging.getLogger("laserstudio").debug(
                f"move vertex for zone {handle.zone_id} {handle.geom_index} is out of range"
            )
            return

        poly = self.__editing_zone.polygons[handle.geom_index]
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
            self.zones.zones[self.__editing_zone.id].polygons[handle.geom_index] = (
                Polygon(exterior, interiors)
            )
        except Exception:
            logging.getLogger("laserstudio").debug(
                f"move vertex for zone {handle.zone_id} {handle.geom_index} is invalid"
            )
            return
        self.__render_edit_polys()
        self.__reposition_handles()

    def __render_edit_polys(self):
        """Render the raw (non-merged) edited polygons during a drag."""
        self.__clear_scan_geometry_items()
        edited = self.__editing_zone
        if edited is None:
            return

        active = self.zones.active_zone is edited
        # Other zones keep being drawn normally while one is edited. The
        # edited zone is skipped by identity: if a zone before
        # it in the list was removed mid-drag, ``__edit_zone_index`` no
        # longer names it, and skipping by index would either miss it (drawn
        # twice, once here and once below) or skip the wrong zone.
        for zone in self.__rendered_zones():
            if zone is edited:
                continue
            for poly in zone.polygons:
                self.__scan_geometry_items.addToGroup(
                    _poly_to_path_item(
                        poly,
                        zone.color,
                        filled=zone.enabled,
                        active=active,
                    )
                )
        for poly in edited.polygons:
            if not isinstance(poly, Polygon) or poly.is_empty:
                continue
            try:
                item = _poly_to_path_item(
                    poly, edited.color, filled=edited.enabled, active=active
                )
            except Exception:
                continue
            self.__scan_geometry_items.addToGroup(item)

    def _end_vertex_edit(self):
        self.__handles_dragging = False
        if self.__editing_zone is None:
            return
        zone = self.__editing_zone
        self.__editing_zone = None

        # Confirm the zone is still present by identity (not ``in``, which
        # would fall back to ``__eq__``): it may have been removed by a
        # concurrent mutation (e.g. a REST client) while the drag was live.
        if zone is None or not any(z is zone for z in self.zones.zones):
            # The edited zone is gone: drop the edit and do a full repaint so
            # the surviving zones come back instead of leaving a blank
            # canvas (the raw edit-polygon rendering used during the drag
            # only draws the other zones, not a merged commit).
            self.__on_zones_changed(zone.id)
            return

        polys: list[Polygon] = []
        for index, poly in enumerate(zone.polygons):
            if isinstance(poly, Polygon) and poly.is_valid and not poly.is_empty:
                polys.append(poly)
                continue
            # An invalid or empty edit (e.g. a dragged vertex crossing an
            # edge, making the polygon self-intersecting) must not delete
            # the polygon: keep its pre-drag shape instead.
            logging.getLogger("laserstudio").warning(
                "Discarding invalid edited polygon, keeping the pre-drag "
                f"shape instead: {poly=}"
            )
            if index < len(self.__pre_polygons):
                polys.append(self.__pre_polygons[index])
        zone.set_polygons(polys)
        self.zones.refresh_geometry()
