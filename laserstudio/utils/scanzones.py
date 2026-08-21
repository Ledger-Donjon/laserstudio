"""Scan zone model — the geometry side of scanning, free of any graphics.

:class:`ScanZones` owns the list of named zones and the scan-path generator.
Because it holds no ``QGraphicsItem``, a single instance can be shared between
several viewers, each rendering it with its own items (see
:class:`laserstudio.widgets.scangeometry.ScanGeometry`).
"""

from __future__ import annotations

import logging
from typing import Any
from PyQt6.QtGui import QColor
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from .scanning import EmptyGeometryError, ScanPathGenerator

__all__ = [
    "EmptyGeometryError",
    "ScanPathGenerator",
    "default_zone_color",
    "parse_color",
    "shapely_to_yaml",
    "yaml_to_shapely",
    "ScanZone",
]

# Colors used for zones created without an explicit color. The first entry is
# the color the single scan geometry used before zones existed, so a one-zone
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
    """:return: The default color for the zone at ``index``, cycling."""
    return QColor(DEFAULT_ZONE_COLORS[index % len(DEFAULT_ZONE_COLORS)])


def parse_color(value: Any, default: QColor) -> QColor:
    """Convert a wire/YAML color value to a :class:`QColor`.

    Accepts a :class:`QColor`, ``"#rrggbb"``, ``"#rrggbbaa"`` or any name Qt
    understands. Anything else yields a copy of ``default``. The
    ``"#rrggbbaa"`` form is input-only: :attr:`ScanZone.settings` never emits
    it, so a color's alpha does not survive a save/reload round trip.
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
        res["exterior"] = list({"x": p[0], "y": p[1]} for p in geometry.exterior.coords)
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
        logging.getLogger("laserstudio").error(f"Invalid serialized geometry: {data=}")
        return GeometryCollection()
    type_, value = next(iter(data.items()))
    if type_ == "polygon":
        if not isinstance(value, dict) or "exterior" not in value:
            logging.getLogger("laserstudio").error(f"Invalid polygon data: {value=}")
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
    """One named scan zone: an id, a name, a color, an enabled flag and a shape.

    The shape is stored as an ordered list of add/subtract operations
    (``ops``), exactly as the single scan geometry used to be, so drawing a
    rectangle and then Shift-drawing a hole in it keeps working. The merged
    result is exposed by :attr:`geometry` and cached until the operations
    change.
    """

    def __init__(
        self,
        id: int,
        name: str | None = None,
        color: QColor | str | None = None,
        enabled: bool = True,
        ops: list[tuple[Polygon, bool]] | None = None,
    ):
        self.id = id
        self._name = name
        self.color = parse_color(value=color, default=default_zone_color(id))
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
            self.set_polygons([g for g in geometry.geoms if isinstance(g, Polygon)])
        else:
            self.set_polygons([])

    @property
    def name(self) -> str:
        """The zone's name."""
        return self._name or f"Zone {self.id}"

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

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
                p for p in geometry.geoms if isinstance(p, Polygon) and not p.is_empty
            ]
        if isinstance(geometry, Polygon):
            return [] if geometry.is_empty else [geometry]
        return []

    @property
    def settings(self) -> dict[str, Any]:
        """Serialise this zone for ``settings.yaml`` and the REST API.

        The color is written as ``#rrggbb``; alpha is deliberately not
        persisted, since the view applies its own fill alpha to a zone and
        a stored alpha would have no meaning to read back.
        """
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color.name(),
            "enabled": self.enabled,
            "geometry": shapely_to_yaml(self.geometry),
        }

    @settings.setter
    def settings(self, settings: dict[str, Any]) -> None:
        """Restore this zone from :attr:`settings`."""
        if "name" in settings:
            self.name = str(settings["name"])
        if "color" in settings:
            self.color = parse_color(settings["color"], self.color)
        if "enabled" in settings:
            self.enabled = bool(settings["enabled"])
        if "geometry" in settings:
            self.set_geometry(yaml_to_shapely(settings["geometry"]))

    @classmethod
    def from_settings(cls, data: dict[str, Any], id: int) -> ScanZone:
        """Build the zone ``id`` from :attr:`settings`, filling in what is missing.

        The ``id`` is given by the caller rather than read from ``data``:
        the model keys its zones by id, so deciding which id a malformed or
        duplicated entry gets is the caller's job.

        :raises KeyError: if ``data`` holds a malformed geometry, so that the
            caller can skip the whole entry instead of loading a zone with a
            silently emptied shape.
        """
        zone = cls(id=id)
        zone.settings = data
        return zone
