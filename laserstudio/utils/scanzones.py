"""Scan zone model — the geometry side of scanning, free of any graphics.

:class:`ScanZones` owns the list of named zones and the scan-path generator.
Because it holds no ``QGraphicsItem``, a single instance can be shared between
several viewers, each rendering it with its own items (see
:class:`laserstudio.widgets.scangeometry.ScanGeometry`).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from .scanning import EmptyGeometryError, ScanPathGenerator

# Colours used for zones created without an explicit colour. The first entry is
# the colour the single scan geometry used before zones existed, so a one-zone
# setup looks unchanged. LedgerColors is deliberately not used: SecurityBlue is
# invisible on the viewer's black background.
DEFAULT_ZONE_COLORS: tuple[QColor, ...] = (
    QColor(100, 255, 0),
    QColor(255, 83, 0),
    QColor(212, 160, 255),
    QColor(0, 200, 255),
    QColor(255, 0, 200),
    QColor(222, 255, 0),
    QColor(255, 80, 80),
    QColor(120, 160, 255),
)


def default_zone_color(index: int) -> QColor:
    """:return: The default colour for the zone at ``index``, cycling."""
    return QColor(DEFAULT_ZONE_COLORS[index % len(DEFAULT_ZONE_COLORS)])


def parse_color(value: Any, default: QColor) -> QColor:
    """Convert a wire/YAML colour value to a :class:`QColor`.

    Accepts a :class:`QColor`, ``"#rrggbb"``, ``"#rrggbbaa"`` or any name Qt
    understands. Anything else yields a copy of ``default``. The
    ``"#rrggbbaa"`` form is input-only: :attr:`ScanZone.settings` never emits
    it, so a colour's alpha does not survive a save/reload round trip.
    """
    if isinstance(value, QColor):
        return QColor(value)
    if not isinstance(value, str):
        return QColor(default)
    text = value.strip()
    if len(text) == 9 and text.startswith("#"):
        # Qt's own 9-character form is "#aarrggbb"; ours is "#rrggbbaa", so the
        # alpha byte is split off and applied separately.
        color = QColor(text[:7])
        if color.isValid():
            try:
                alpha = int(text[7:], 16)
            except ValueError:
                alpha = -1
            if 0 <= alpha <= 255:
                color.setAlpha(alpha)
                return color
    color = QColor(text)
    return color if color.isValid() else QColor(default)


def shapely_to_yaml(geometry: BaseGeometry) -> dict[str, Any]:
    """Serialise a shapely geometry to the YAML/JSON form used by settings."""
    if isinstance(geometry, Polygon):
        res: dict[str, Any] = {}
        res["exterior"] = list(
            {"x": p[0], "y": p[1]} for p in geometry.exterior.coords
        )
        interiors: list[list[dict[str, float]]] = []
        for interior in geometry.interiors:
            interiors.append(list({"x": p[0], "y": p[1]} for p in interior.coords))
        res["interiors"] = interiors
        return {"polygon": res}
    if isinstance(geometry, MultiPolygon):
        return {"multipolygon": [shapely_to_yaml(poly) for poly in geometry.geoms]}
    if isinstance(geometry, GeometryCollection):
        # This is what an empty geometry serialises to.
        return {"geometrycollection": None}
    logging.getLogger("laserstudio").warning(
        f"Unsupported shapely geometry for serialization: {type(geometry)=}"
    )
    return {"geometrycollection": None}


def _points_from_yaml(points: Any) -> list[tuple[float, float]] | None:
    """Convert a list of ``{"x", "y"}`` dicts to coordinate tuples.

    Defence in depth for the YAML-loading path, which has no validator in
    front of it: a non-dict element (``point["x"]`` raising ``TypeError``) or
    a value ``float()`` rejects (``ValueError``, or ``TypeError`` for e.g. a
    ``None``) is logged and treated as malformed, exactly like this module's
    other malformed-input guards, rather than raising.

    A dict *missing* the ``"x"``/``"y"`` key deliberately still raises
    ``KeyError`` here: callers that load a whole zone (e.g.
    ``ScanZone.from_settings``) rely on that propagating so the malformed
    zone entry is skipped instead of silently becoming an empty shape.

    :return: The coordinates, or ``None`` if ``points`` is not a list of
        such dicts.
    :raises KeyError: if an element is a dict missing ``"x"`` or ``"y"``.
    """
    if not isinstance(points, list):
        logging.getLogger("laserstudio").error(
            f"Invalid point list for scan zone geometry: {points=}"
        )
        return None
    result: list[tuple[float, float]] = []
    for point in points:
        try:
            result.append((float(point["x"]), float(point["y"])))
        except (TypeError, ValueError):
            logging.getLogger("laserstudio").error(
                f"Invalid point in scan zone geometry: {point=}"
            )
            return None
    return result


def yaml_to_shapely(data: dict[str, Any]) -> BaseGeometry:
    """Deserialise the YAML/JSON form produced by :func:`shapely_to_yaml`."""
    if len(data) != 1:
        logging.getLogger("laserstudio").error(
            f"Invalid serialized geometry: {data=}"
        )
        return GeometryCollection()
    type_, value = next(iter(data.items()))
    if type_ == "polygon":
        if not isinstance(value, dict) or "exterior" not in value:
            logging.getLogger("laserstudio").error(
                f"Invalid polygon data: {value=}"
            )
            return GeometryCollection()
        exterior = _points_from_yaml(value["exterior"])
        if exterior is None:
            return GeometryCollection()
        interiors: list[list[tuple[float, float]]] = []
        for value_sub in value.get("interiors") or []:
            interior = _points_from_yaml(value_sub)
            if interior is None:
                return GeometryCollection()
            interiors.append(interior)
        return Polygon(shell=exterior, holes=interiors)
    if type_ == "multipolygon":
        if not isinstance(value, (list, tuple)):
            logging.getLogger("laserstudio").error(
                f"Invalid multipolygon data: {value=}"
            )
            return GeometryCollection()
        polygons: list[Polygon] = []
        for value_sub in value:
            geom = yaml_to_shapely(value_sub)
            if isinstance(geom, Polygon):
                if not geom.is_empty:
                    polygons.append(geom)
            elif isinstance(geom, MultiPolygon):
                polygons.extend(geom.geoms)
            else:
                logging.getLogger("laserstudio").warning(
                    f"Invalid polygon type: {type(geom)=}, {geom=}"
                )
        return MultiPolygon(polygons=polygons)
    if type_ == "geometrycollection":
        return GeometryCollection()
    logging.getLogger("laserstudio").error(
        f"Unknown serialized geometry type: {type_=}"
    )
    return GeometryCollection()


def _is_valid_polygon(polygon: Any) -> bool:
    """:return: True if ``polygon`` is a non-empty, valid ``Polygon``."""
    return isinstance(polygon, Polygon) and not polygon.is_empty and polygon.is_valid


class ScanZone:
    """One named scan zone: a colour, an enabled flag and a shape.

    The shape is stored as an ordered list of add/subtract operations
    (``ops``), exactly as the single scan geometry used to be, so drawing a
    rectangle and then Shift-drawing a hole in it keeps working. The merged
    result is exposed by :attr:`geometry` and cached until the operations
    change.
    """

    def __init__(
        self,
        name: str,
        color: QColor | None = None,
        enabled: bool = True,
        ops: list[tuple[Polygon, bool]] | None = None,
    ):
        self.name = name
        self.color = QColor(color) if color is not None else default_zone_color(0)
        self.enabled = enabled
        self.ops: list[tuple[Polygon, bool]] = list(ops or [])
        self._geometry_cache: BaseGeometry | None = None

    def invalidate(self) -> None:
        """Drop the cached merged geometry. Call after mutating ``ops``."""
        self._geometry_cache = None

    def add(self, polygon: Polygon) -> bool:
        """Union ``polygon`` into this zone. :return: True if it was applied."""
        return self.__append(polygon, True)

    def remove(self, polygon: Polygon) -> bool:
        """Subtract ``polygon`` from this zone. :return: True if applied."""
        return self.__append(polygon, False)

    def __append(self, polygon: Polygon, is_add: bool) -> bool:
        if not _is_valid_polygon(polygon):
            return False
        self.ops.append((polygon, is_add))
        self.invalidate()
        return True

    def set_polygons(self, polygons: list[Polygon]) -> None:
        """Replace the operations with one add-operation per polygon."""
        self.ops = [
            (p, True)
            for p in polygons
            if isinstance(p, Polygon) and p.is_valid and not p.is_empty
        ]
        self.invalidate()

    def set_geometry(self, geometry: BaseGeometry) -> None:
        """Replace the operations with the polygons of ``geometry``."""
        if isinstance(geometry, Polygon):
            self.set_polygons([geometry])
        elif isinstance(geometry, (MultiPolygon, GeometryCollection)):
            self.set_polygons(
                [g for g in geometry.geoms if isinstance(g, Polygon)]
            )
        else:
            self.set_polygons([])

    @property
    def geometry(self) -> BaseGeometry:
        """The merged shape of this zone (a ``Polygon`` or ``MultiPolygon``)."""
        if self._geometry_cache is None:
            result: BaseGeometry = MultiPolygon()
            for polygon, is_add in self.ops:
                if not polygon.is_valid:
                    continue
                result = (result | polygon) if is_add else (result - polygon)
            self._geometry_cache = result
        return self._geometry_cache

    @property
    def polygons(self) -> list[Polygon]:
        """The zone's merged shape as a flat list of non-empty polygons."""
        geometry = self.geometry
        if isinstance(geometry, MultiPolygon):
            return [
                p
                for p in geometry.geoms
                if isinstance(p, Polygon) and not p.is_empty
            ]
        if isinstance(geometry, Polygon):
            return [] if geometry.is_empty else [geometry]
        return []

    @property
    def settings(self) -> dict[str, Any]:
        """Serialise this zone for ``settings.yaml`` and the REST API.

        The colour is written as ``#rrggbb``; alpha is deliberately not
        persisted, since the view applies its own fill alpha to a zone and
        a stored alpha would have no meaning to read back.
        """
        return {
            "name": self.name,
            "color": self.color.name(),
            "enabled": self.enabled,
            "geometry": shapely_to_yaml(self.geometry),
        }

    @classmethod
    def from_settings(cls, data: dict[str, Any], index: int = 0) -> "ScanZone":
        """Build a zone from :attr:`settings`, filling in missing fields.

        :param index: Position of the zone, used for the default name/colour.
        """
        zone = cls(
            name=str(data.get("name") or f"Zone {index + 1}"),
            color=parse_color(data.get("color"), default_zone_color(index)),
            enabled=bool(data.get("enabled", True)),
        )
        geometry = data.get("geometry")
        if isinstance(geometry, dict):
            zone.set_geometry(yaml_to_shapely(geometry))
        return zone


class ScanZones(QObject):
    """The ordered list of scan zones plus the scan-path generator.

    Point generation always runs on :attr:`flattened`, the union of every
    *enabled* zone. Drawing gestures target the *active* zone only.

    Holds no graphics, so one instance can be shared by several viewers. Views
    subscribe to :attr:`changed` (the zone list, a zone's shape, name, colour,
    enabled flag or the active index changed — redraw everything) and
    :attr:`path_changed` (the scan path points moved — redraw the path).
    """

    changed = pyqtSignal()
    path_changed = pyqtSignal()

    # Matches the default names handed out by add_zone, so the next default
    # number can be derived from the current list instead of stored.
    _ZONE_NAME_RE = re.compile(r"^Zone (\d+)$")

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.zones: list[ScanZone] = []
        self._active_index = 0
        self.scan_path_generator = ScanPathGenerator()
        # Shared appearance of the scan path itself (not of the zones).
        self._path_color = QColor(100, 255, 0)
        self._point_diameter = 10.0

    # -- Active zone -------------------------------------------------------- #

    @property
    def active_index(self) -> int:
        """Index of the zone that drawing gestures target."""
        return self._active_index

    @active_index.setter
    def active_index(self, value: int) -> None:
        index = self.__clamp_index(value)
        if index != self._active_index:
            self._active_index = index
            self.changed.emit()

    def __clamp_index(self, value: int) -> int:
        if not self.zones:
            return 0
        return max(0, min(int(value), len(self.zones) - 1))

    @property
    def active_zone(self) -> ScanZone | None:
        """The active zone, or ``None`` when there is no zone at all."""
        if not self.zones:
            return None
        return self.zones[self._active_index]

    def ensure_active_zone(self) -> ScanZone:
        """Return the active zone, creating ``Zone 1`` if the list is empty."""
        if not self.zones:
            self.add_zone()
        return self.zones[self._active_index]

    # -- Zone list ---------------------------------------------------------- #

    def zone(self, index: int) -> ScanZone:
        """:raises IndexError: if ``index`` is out of range."""
        if not (0 <= index < len(self.zones)):
            raise IndexError(f"No scan zone at index {index}")
        return self.zones[index]

    def __next_zone_number(self) -> int:
        """Derive the next default zone number from the existing names.

        Scanning for the highest existing ``Zone <n>`` name (rather than
        keeping a stored counter) means a delete-then-add cycle never reuses
        a name that is still in the list, and the derivation self-heals after
        a settings load replaces ``self.zones`` wholesale.
        """
        highest = 0
        for zone in self.zones:
            match = self._ZONE_NAME_RE.match(zone.name)
            if match:
                highest = max(highest, int(match.group(1)))
        return highest + 1

    def add_zone(
        self,
        name: str | None = None,
        color: QColor | str | None = None,
        enabled: bool = True,
        geometry: BaseGeometry | dict[str, Any] | None = None,
    ) -> int:
        """Append a zone. :return: The index of the new zone."""
        index = len(self.zones)
        number = self.__next_zone_number()
        zone = ScanZone(
            name=name if name is not None else f"Zone {number}",
            color=(
                parse_color(color, default_zone_color(number - 1))
                if color is not None
                else default_zone_color(number - 1)
            ),
            enabled=enabled,
        )
        if geometry is not None:
            zone.set_geometry(self.__as_geometry(geometry))
        self.zones.append(zone)
        self.refresh_geometry()
        return index

    def update_zone(
        self,
        index: int,
        name: str | None = None,
        color: QColor | str | None = None,
        enabled: bool | None = None,
        geometry: BaseGeometry | dict[str, Any] | None = None,
    ) -> ScanZone:
        """Update any subset of a zone's attributes.

        :raises IndexError: if ``index`` is out of range.
        """
        zone = self.zone(index)
        if name is not None:
            zone.name = name
        if color is not None:
            zone.color = parse_color(color, zone.color)
        if enabled is not None:
            zone.enabled = enabled
        if geometry is not None:
            zone.set_geometry(self.__as_geometry(geometry))
        # Only a shape or enabled change alters what gets scanned; renaming or
        # recolouring must not throw the current scan path away.
        if enabled is not None or geometry is not None:
            self.refresh_geometry()
        else:
            self.changed.emit()
        return zone

    def remove_zone(self, index: int) -> None:
        """Delete a zone, keeping the active selection sensible.

        :raises IndexError: if ``index`` is out of range.
        """
        self.zone(index)
        del self.zones[index]
        if not self.zones:
            self._active_index = 0
        elif index < self._active_index:
            self._active_index -= 1
        elif index == self._active_index:
            self._active_index = self.__clamp_index(max(0, index - 1))
        self.refresh_geometry()

    def clear(self) -> None:
        """Remove every zone."""
        self.zones.clear()
        self._active_index = 0
        self.refresh_geometry()

    @staticmethod
    def __as_geometry(value: BaseGeometry | dict[str, Any]) -> BaseGeometry:
        """Accept either a shapely geometry or its serialised form."""
        if isinstance(value, dict):
            return yaml_to_shapely(value)
        return value

    # -- Drawing ------------------------------------------------------------ #

    def add(self, polygon: Polygon) -> None:
        """Union ``polygon`` into the active zone, creating one if needed.

        A rejected polygon (not a ``Polygon``, empty, or invalid) is checked
        before a zone is created, so a rejected draw on an empty model leaves
        no side effect behind.
        """
        if not _is_valid_polygon(polygon):
            return
        if self.ensure_active_zone().add(polygon):
            self.refresh_geometry()

    def remove(self, polygon: Polygon) -> None:
        """Subtract ``polygon`` from the active zone, creating one if needed.

        See :meth:`add` for why the polygon is validated before a zone is
        created.
        """
        if not _is_valid_polygon(polygon):
            return
        if self.ensure_active_zone().remove(polygon):
            self.refresh_geometry()

    # -- Flattened geometry and point generation ---------------------------- #

    @property
    def flattened(self) -> MultiPolygon | Polygon:
        """The union of every enabled zone — what actually gets scanned."""
        result: BaseGeometry = MultiPolygon()
        for zone in self.zones:
            if not zone.enabled:
                continue
            geometry = zone.geometry
            if geometry.is_empty:
                continue
            result = result | geometry
        if isinstance(result, (Polygon, MultiPolygon)):
            return result
        return MultiPolygon()

    def refresh_geometry(self) -> None:
        """Push the flattened union into the generator and notify the views."""
        for zone in self.zones:
            zone.invalidate()
        self.scan_path_generator.geometry = self.flattened
        self.changed.emit()
        self.path_changed.emit()

    def is_empty(self) -> bool:
        """:return: True when no point can be generated."""
        return self.scan_path_generator.is_empty()

    def next_point(self) -> tuple[float, float] | None:
        """Pop the next scan point, or ``None`` when there is nothing to scan."""
        if self.scan_path_generator.is_empty():
            logging.getLogger("laserstudio").error(
                "Cannot get next point: no enabled scan zone."
            )
            return None
        try:
            point = self.scan_path_generator.pop()
        except EmptyGeometryError:
            logging.getLogger("laserstudio").error("Cannot generate a point.")
            return None
        self.path_changed.emit()
        return point

    # -- Shared path appearance --------------------------------------------- #

    @property
    def density(self) -> int:
        """Points per generated path; higher means closer consecutive points."""
        return self.scan_path_generator.density

    @density.setter
    def density(self, value: int) -> None:
        self.scan_path_generator.density = value
        self.path_changed.emit()

    @property
    def path_color(self) -> QColor:
        """Colour of the scan path markers (shared by every view)."""
        return self._path_color

    @path_color.setter
    def path_color(self, value: QColor) -> None:
        self._path_color = QColor(value)
        self.changed.emit()

    @property
    def point_diameter(self) -> float:
        """Diameter of the scan path markers, in µm."""
        return self._point_diameter

    @point_diameter.setter
    def point_diameter(self, value: float) -> None:
        self._point_diameter = float(value)
        self.changed.emit()

    # -- Persistence -------------------------------------------------------- #

    @property
    def settings(self) -> dict[str, Any]:
        """Serialise the whole model.

        ``geometry`` is output-only: it mirrors :attr:`flattened` so callers
        written against the single-geometry API keep working.
        """
        return {
            "density": self.density,
            "active": self._active_index,
            "zones": [zone.settings for zone in self.zones],
            "geometry": shapely_to_yaml(self.flattened),
        }

    @settings.setter
    def settings(self, data: dict[str, Any]) -> None:
        """Restore the whole model.

        Everything that can fail is parsed into a local ``new_zones`` before
        anything on ``self`` is touched, so a malformed entry never leaves
        the model half-updated (e.g. ``density`` changed but ``zones`` not,
        or vice versa) — this matters once the payload can come from an
        untrusted REST client.
        """
        logging.getLogger("laserstudio").debug(f"Scan zones settings: {data}...")

        zones_data = data.get("zones")
        new_zones: list[ScanZone] | None = None
        if isinstance(zones_data, list):
            new_zones = []
            for index, item in enumerate(zones_data):
                if not isinstance(item, dict):
                    continue
                try:
                    new_zones.append(ScanZone.from_settings(item, index))
                except Exception:
                    logging.getLogger("laserstudio").warning(
                        f"Skipping malformed scan zone entry: {item=}"
                    )
        else:
            try:
                legacy = self.__legacy_geometry(data)
            except Exception:
                logging.getLogger("laserstudio").warning(
                    f"Skipping malformed legacy scan geometry: {data=}"
                )
                legacy = None
            else:
                if legacy is None:
                    logging.getLogger("laserstudio").warning(
                        "Invalid data for scan geometry (expected a 'zones' "
                        f"list or a 'geometry' key): {data=}"
                    )
            if legacy is not None:
                zone = ScanZone(name="Zone 1", color=default_zone_color(0))
                zone.set_geometry(legacy)
                new_zones = [zone]

        density = data.get("density")
        if isinstance(density, int) and not isinstance(density, bool):
            try:
                self.scan_path_generator.density = density
            except ValueError:
                logging.getLogger("laserstudio").warning(
                    f"Ignoring invalid scan density: {density}"
                )

        if new_zones is not None:
            # Mutate in place rather than rebinding: ``zones`` is public, and
            # ``clear()``/``remove_zone()`` keep the same list object, so views
            # holding a reference stay correct across a settings load too.
            self.zones[:] = new_zones

        active = data.get("active")
        self._active_index = self.__clamp_index(
            active if isinstance(active, int) and not isinstance(active, bool) else 0
        )
        self.refresh_geometry()

    @staticmethod
    def __legacy_geometry(data: dict[str, Any]) -> BaseGeometry | None:
        """Read the pre-zones payload: a bare or nested single geometry."""
        for key in ("polygon", "multipolygon", "geometrycollection"):
            if key in data:
                return yaml_to_shapely(data)
        geometry = data.get("geometry")
        if isinstance(geometry, dict):
            return yaml_to_shapely(geometry)
        return None
