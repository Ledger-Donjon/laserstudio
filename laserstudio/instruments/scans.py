from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from typing import Any
import logging
from .instrument import Instrument
from ..utils.yaml_types import Config
from ..utils.scanzones import (
    parse_color,
    default_zone_color,
    _is_valid_polygon,
    ScanZone,
    BaseGeometry,
    ScanPathGenerator,
    MultiPolygon,
    Polygon,
    shapely_to_yaml,
    yaml_to_shapely,
    EmptyGeometryError,
)

__all__ = [
    "ScansInstrument",
    "default_zone_color",
    "parse_color",
    "ScanZone",
    "BaseGeometry",
    "ScanPathGenerator",
    "MultiPolygon",
    "Polygon",
    "shapely_to_yaml",
    "yaml_to_shapely",
    "EmptyGeometryError",
]

#: A pre-zones payload describing an empty scan geometry. Kept as a public
#: attribute for external scripts that may import it.
EMPTY_SCAN_GEOMETRY: Config = {
    "geometry": {"polygon": {"exterior": [], "interiors": []}}
}


class ScansInstrument(Instrument):
    """The ordered list of scan zones plus the scan-path generator.

    Point generation always runs on :attr:`flattened`, the union of every
    *enabled* zone. Drawing gestures target the *active* zone only.

    Holds no graphics, so one instance can be shared by several viewers.
    Views subscribe to :attr:`zone_changed` (a zone's shape, name, color, enabled flag changed),
     :attr:`active_zone_changed` (the active zone changed)
     and :attr:`path_changed` (the scan path points moved, or color or diameter changed).
    """

    zone_changed = pyqtSignal(int)
    path_changed = pyqtSignal()
    active_zone_changed = pyqtSignal(int)

    def __init__(self, config: Config):
        super().__init__(config)
        self.zones: dict[int, ScanZone] = {}
        self.scan_path_generator = ScanPathGenerator()
        self._active_zone = None
        # Shared appearance of the scan path itself (not of the zones).
        self._path_color = QColor(100, 255, 0)
        self._point_diameter = 10.0

    # -- Zone list ---------------------------------------------------------- #

    def zone(self, id: int) -> ScanZone:
        """:raises KeyError: if ``id`` is not in the zones dictionary."""
        if id not in self.zones:
            raise KeyError(f"No scan zone with id {id}.")
        return self.zones[id]

    @property
    def next_zone_id(self) -> int:
        """The id :meth:`add_zone` will hand out next.

        Exposed so a view can preview what the zone a gesture is about to
        create will look like (its default color is derived from its id).
        """
        if not self.zones:
            return 1
        return max(self.zones.keys()) + 1

    def add_zone(
        self,
        id: int | None = None,
        name: str | None = None,
        color: QColor | str | None = None,
        enabled: bool = True,
        geometry: BaseGeometry | dict[str, Any] | None = None,
    ) -> ScanZone:
        """Append a zone. :return: The new zone."""
        if id is None:
            id = self.next_zone_id

        if id in self.zones:
            raise ValueError(f"Zone with id {id} already exists.")

        zone = ScanZone(
            id=id,
            name=name,
            color=color,
            enabled=enabled,
        )
        if geometry is not None:
            zone.set_geometry(self.__as_geometry(geometry))
        self.zones[zone.id] = zone
        self.__refresh_geometry(zone.id)
        return zone

    def update_zone(self, zone: ScanZone) -> None:
        """Update a zone resulting actions."""
        self.__refresh_geometry(zone.id)

    def update_zone_params(
        self,
        zone_id: int,
        name: str | None = None,
        color: QColor | str | None = None,
        enabled: bool | None = None,
        geometry: BaseGeometry | dict[str, Any] | None = None,
    ) -> None:
        """Update a zone."""
        zone = self.zone(zone_id)
        if name is not None:
            zone.name = name
        if color is not None:
            zone.color = parse_color(color, default=zone.color)
        if geometry is not None:
            zone.set_geometry(self.__as_geometry(geometry))
        if enabled is not None:
            zone.enabled = enabled
        self.__refresh_geometry(zone.id)

    def remove_zone(self, zone: ScanZone | int) -> None:
        """Delete a zone, keeping the active selection sensible.

        :raises KeyError: if ``zone`` is not in the zones dictionary.
        """
        if isinstance(zone, int):
            zone = self.zone(zone)
        del self.zones[zone.id]
        self.__refresh_geometry(zone.id)
        if self.active_zone is not None and zone.id == self.active_zone.id:
            self.active_zone = None

    def clear(self) -> None:
        """Remove every zone."""
        self.zones.clear()
        self.active_zone = None
        self.refresh_geometry()

    # -- Zone active ------------------------------------------------------- #

    @property
    def active_zone(self) -> ScanZone | None:
        """The active zone."""
        return self._active_zone

    @active_zone.setter
    def active_zone(self, value: ScanZone | None) -> None:
        self._active_zone = value
        self.active_zone_changed.emit(value.id if value is not None else -1)

    # -- Drawing ------------------------------------------------------------ #

    def add(self, polygon: Polygon) -> None:
        """Union ``polygon`` into the active zone, creating one if needed.

        A rejected polygon (not a ``Polygon``, empty, or invalid) is checked
        before a zone is created, so a rejected draw on an empty model leaves
        no side effect behind.
        """
        if not _is_valid_polygon(polygon):
            return
        if self.active_zone is None:
            self.active_zone = self.add_zone()
        if self.active_zone.add(polygon):
            self.refresh_geometry()

    def remove(self, polygon: Polygon) -> None:
        """Subtract ``polygon`` from the active zone.

        See :meth:`add` for why the polygon is validated before a zone is
        created.
        """
        if not _is_valid_polygon(polygon):
            return
        if self.active_zone is not None and self.active_zone.remove(polygon):
            self.refresh_geometry()

    # -- Flattened geometry and point generation ---------------------------- #

    @property
    def density(self) -> int:
        """Points per generated path; higher means closer consecutive points."""
        return self.scan_path_generator.density

    @density.setter
    def density(self, value: int) -> None:
        self.scan_path_generator.density = value
        self.path_changed.emit()

    @property
    def flattened(self) -> MultiPolygon | Polygon:
        """The union of every enabled zone — what actually gets scanned."""
        result: BaseGeometry = MultiPolygon()
        for zone in self.zones.values():
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
        self.__refresh_geometry(-1)

    def __refresh_geometry(self, zone_id: int) -> None:
        """Same, naming the zone that changed.

        A single notification per mutation: announcing the change twice
        would make every view rebuild twice, which is not just wasted work —
        the second rebuild throws away what the first one restored (the
        focused name editor of a zone being renamed, say).
        """
        for zone in self.zones.values():
            zone.invalidate()
        self.scan_path_generator.geometry = self.flattened
        self.zone_changed.emit(zone_id)
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
    def path_color(self) -> QColor:
        """Color of the scan path markers (shared by every view)."""
        return self._path_color

    @path_color.setter
    def path_color(self, value: QColor) -> None:
        self._path_color = QColor(value)
        self.path_changed.emit()

    @property
    def point_diameter(self) -> float:
        """Diameter of the scan path markers, in µm."""
        return self._point_diameter

    @point_diameter.setter
    def point_diameter(self, value: float) -> None:
        self._point_diameter = float(value)
        self.path_changed.emit()

    # -- Persistence -------------------------------------------------------- #

    @property
    def settings(self) -> dict[str, Any]:
        """Serialise the whole model.

        ``geometry`` is output-only: it mirrors :attr:`flattened` so callers
        written against the single-geometry API keep working.
        """
        return {
            "density": self.density,
            "active": self.active_zone.id if self.active_zone is not None else None,
            "zones": [zone.settings for zone in self.zones.values()],
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
        new_zones: dict[int, ScanZone] | None = None
        legacy_zone: ScanZone | None = None
        if isinstance(zones_data, list):
            new_zones = {}
            for index, item in enumerate(zones_data):
                if not isinstance(item, dict):
                    logging.getLogger("laserstudio").warning(
                        f"Skipping malformed scan zone entry: {item=}"
                    )
                    continue
                id = self.__zone_id_from_settings(item, index, new_zones)
                try:
                    new_zones[id] = ScanZone.from_settings(item, id)
                except Exception:
                    logging.getLogger("laserstudio").warning(
                        f"Skipping malformed scan zone entry: {item=}"
                    )
        else:
            legacy_zone = self.__zone_from_legacy_settings(data)
            if legacy_zone is not None:
                new_zones = {legacy_zone.id: legacy_zone}

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
            # ``clear()``/``remove_zone()`` keep the same dictionary object, so
            # views holding a reference stay correct across a settings load too.
            self.zones.clear()
            self.zones.update(new_zones)

        # The active zone is stored by id; an unknown one means "no active
        # zone" rather than an arbitrary fallback, which would silently send
        # the next drawing gesture into someone else's zone.
        active = data.get("active")
        if isinstance(active, int) and not isinstance(active, bool):
            self.active_zone = self.zones.get(active)
        else:
            # A pre-zones payload carries no active zone, but the single zone
            # it restores is the obvious target for the next drawing gesture.
            self.active_zone = legacy_zone
        self.refresh_geometry()

    @staticmethod
    def __zone_from_legacy_settings(data: dict[str, Any]) -> ScanZone | None:
        """Read a pre-zones payload — a bare or nested single geometry.

        Settings files written before scan zones existed hold
        ``{"density": …, "geometry": …}``, and scripts still PUT that shape;
        both must keep restoring the area they describe, as one zone.

        :return: The restored zone, or ``None`` when ``data`` holds no
            readable geometry.
        """
        geometry: BaseGeometry | None = None
        try:
            for key in ("polygon", "multipolygon", "geometrycollection"):
                if key in data:
                    geometry = yaml_to_shapely(data)
                    break
            else:
                nested = data.get("geometry")
                if isinstance(nested, dict):
                    geometry = yaml_to_shapely(nested)
        except Exception:
            logging.getLogger("laserstudio").warning(
                f"Skipping malformed legacy scan geometry: {data=}"
            )
            return None

        if geometry is None:
            logging.getLogger("laserstudio").warning(
                "Invalid data for scan geometry (expected a 'zones' list or a "
                f"'geometry' key): {data=}"
            )
            return None

        zone = ScanZone(id=1)
        zone.set_geometry(geometry)
        return zone

    @staticmethod
    def __zone_id_from_settings(
        item: dict[str, Any], index: int, taken: dict[int, ScanZone]
    ) -> int:
        """:return: The id to give the zone described by ``item``.

        A missing, non-integer or already-used id falls back to the first free
        one, so a hand-edited or partially written file still loads all its
        zones instead of collapsing several of them onto the same key.
        """
        id = item.get("id")
        if isinstance(id, int) and not isinstance(id, bool) and id not in taken:
            return id
        candidate = index + 1
        while candidate in taken:
            candidate += 1
        return candidate

    @staticmethod
    def is_valid_scan_zone_color(color: Any) -> bool:
        """Mirrors the color forms :func:`~laserstudio.utils.scanzones.parse_color`
        accepts, without inheriting its lenient fallback-to-default behaviour."""
        if not isinstance(color, str):
            return False
        text = color.strip()
        if len(text) == 9 and text.startswith("#"):
            if not QColor(text[:7]).isValid():
                return False
            try:
                alpha = int(text[7:], 16)
            except ValueError:
                return False
            return 0 <= alpha <= 255
        return QColor(text).isValid()

    @staticmethod
    def is_valid_scan_zone_point_list(points: Any) -> bool:
        if not isinstance(points, list):
            return False
        for point in points:
            if not isinstance(point, dict):
                return False
            x, y = point.get("x"), point.get("y")
            if isinstance(x, bool) or isinstance(y, bool):
                return False
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                return False
        return True

    @staticmethod
    def is_valid_scan_zone_ring_set(value: Any) -> bool:
        if not isinstance(value, dict) or "exterior" not in value:
            return False
        if not ScansInstrument.is_valid_scan_zone_point_list(value["exterior"]):
            return False
        interiors = value.get("interiors") or []
        if not isinstance(interiors, list):
            return False
        return all(
            ScansInstrument.is_valid_scan_zone_point_list(ring) for ring in interiors
        )

    @staticmethod
    def is_valid_scan_zone_geometry(geometry: Any) -> bool:
        if not isinstance(geometry, dict) or len(geometry) != 1:
            return False
        type_, value = next(iter(geometry.items()))
        if type_ == "geometrycollection":
            return True
        if type_ == "polygon":
            return ScansInstrument.is_valid_scan_zone_ring_set(value)
        if type_ == "multipolygon":
            return isinstance(value, list) and all(
                ScansInstrument.is_valid_scan_zone_geometry(item) for item in value
            )
        return False

    @staticmethod
    def __as_geometry(geometry: BaseGeometry | dict[str, Any]) -> BaseGeometry:
        if isinstance(geometry, dict):
            return yaml_to_shapely(geometry)
        return geometry
