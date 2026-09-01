"""Unit tests for laserstudio.utils.scanzones and ScansInstrument.

``ScanZone``, colour parsing and YAML geometry live in ``scanzones``. The
zone *list* and scan-path generator belong to ``ScansInstrument``.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication
from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon

from laserstudio.instruments.scans import ScansInstrument
from laserstudio.utils.scanzones import (
    DEFAULT_ZONE_COLORS,
    ScanZone,
    default_zone_color,
    parse_color,
    shapely_to_yaml,
    yaml_to_shapely,
)


def _square(x: float = 0.0, y: float = 0.0, size: float = 1.0) -> Polygon:
    return Polygon([(x, y), (x + size, y), (x + size, y + size), (x, y + size)])


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def scans(qapp) -> ScansInstrument:
    return ScansInstrument({})


class TestDefaultZoneColor:
    def test_cycles_through_the_palette(self):
        assert default_zone_color(0) == DEFAULT_ZONE_COLORS[0]
        assert default_zone_color(1) == DEFAULT_ZONE_COLORS[1]
        n = len(DEFAULT_ZONE_COLORS)
        assert default_zone_color(n) == DEFAULT_ZONE_COLORS[0]


class TestScanZone:
    def test_new_zone_is_empty_and_enabled(self):
        zone = ScanZone(id=1)
        assert zone.id == 1
        assert zone.name == "Zone 1"
        assert zone.enabled is True
        assert zone.color == default_zone_color(1)
        assert zone.geometry.is_empty
        assert zone.polygons == []

    def test_explicit_name_and_color(self):
        zone = ScanZone(id=3, name="Pads", color="#123456", enabled=False)
        assert zone.name == "Pads"
        zone.name = "Other"
        assert zone.name == "Other"
        assert zone.color == QColor("#123456")
        assert zone.enabled is False

    def test_add_polygon_becomes_the_geometry(self):
        zone = ScanZone(id=1)
        assert zone.add(_square()) is True
        assert zone.geometry.area == pytest.approx(1.0)
        assert len(zone.polygons) == 1

    def test_remove_subtracts_from_the_geometry(self):
        zone = ScanZone(id=1)
        zone.add(_square(size=2.0))
        zone.remove(_square(size=1.0))
        assert zone.geometry.area == pytest.approx(3.0)

    def test_add_rejects_invalid_and_empty_polygons(self):
        zone = ScanZone(id=1)
        assert zone.add(Polygon()) is False
        bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])
        assert zone.add(bowtie) is False
        assert zone.geometry.is_empty

    def test_geometry_is_cached_until_invalidated(self):
        zone = ScanZone(id=1)
        zone.add(_square())
        first = zone.geometry
        assert zone.geometry is first
        zone.add(_square(x=5.0))
        assert zone.geometry is not first
        assert zone.geometry.area == pytest.approx(2.0)

    def test_set_polygons_replaces_the_operations(self):
        zone = ScanZone(id=1)
        zone.add(_square(size=3.0))
        zone.remove(_square(size=1.0))
        zone.set_polygons([_square(size=2.0)])
        assert zone.geometry.area == pytest.approx(4.0)
        assert zone.ops == [(_square(size=2.0), True)]

    def test_set_geometry_flattens_a_multipolygon(self):
        zone = ScanZone(id=1)
        zone.set_geometry(MultiPolygon([_square(), _square(x=5.0)]))
        assert len(zone.polygons) == 2
        assert zone.geometry.area == pytest.approx(2.0)

    def test_set_geometry_accepts_a_geometry_collection_of_polygons(self):
        zone = ScanZone(id=1)
        zone.set_geometry(GeometryCollection([_square(), _square(x=5.0)]))
        assert len(zone.polygons) == 2

    def test_set_geometry_drops_unsupported_types(self):
        zone = ScanZone(id=1)
        zone.add(_square())
        zone.set_geometry(Point(0, 0))
        assert zone.ops == []
        assert zone.geometry.is_empty

    def test_remove_rejects_invalid_and_empty_polygons(self):
        zone = ScanZone(id=1)
        zone.add(_square(size=2.0))
        assert zone.remove(Polygon()) is False
        bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])
        assert zone.remove(bowtie) is False
        assert zone.geometry.area == pytest.approx(4.0)

    def test_ops_constructor_parameter_seeds_the_operations(self):
        square = _square(size=2.0)
        hole = _square(size=1.0)
        zone = ScanZone(id=1, ops=[(square, True), (hole, False)])
        assert zone.ops == [(square, True), (hole, False)]
        assert zone.geometry.area == pytest.approx(3.0)


class TestParseColor:
    def test_hex_rgb(self):
        assert parse_color("#ff0000", QColor("#00ff00")) == QColor(255, 0, 0)

    def test_qcolor_is_copied(self):
        original = QColor("#ff0000")
        parsed = parse_color(original, QColor("#00ff00"))
        assert parsed == original
        assert parsed is not original

    def test_hex_rgba_alpha_is_last(self):
        color = parse_color("#ff000080", QColor("#00ff00"))
        assert (color.red(), color.green(), color.blue()) == (255, 0, 0)
        assert color.alpha() == 0x80

    def test_invalid_falls_back_to_default(self):
        default = QColor("#00ff00")
        assert parse_color("not-a-color", default) == default
        assert parse_color(None, default) == default
        assert parse_color(42, default) == default

    def test_malformed_alpha_falls_back_to_default(self):
        default = QColor("#00ff00")
        assert parse_color("#ff0000-1", default) == default


class TestSerialisation:
    def test_polygon_round_trip(self):
        poly = _square(size=2.0)
        data = shapely_to_yaml(poly)
        assert set(data) == {"polygon"}
        restored = yaml_to_shapely(data)
        assert restored.equals(poly)

    def test_polygon_with_hole_round_trip(self):
        poly = _square(size=4.0).difference(_square(x=1.0, y=1.0, size=1.0))
        restored = yaml_to_shapely(shapely_to_yaml(poly))
        assert restored.equals(poly)

    def test_multipolygon_round_trip(self):
        multi = MultiPolygon([_square(), _square(x=5.0)])
        data = shapely_to_yaml(multi)
        assert set(data) == {"multipolygon"}
        restored = yaml_to_shapely(data)
        assert restored.equals(multi)

    def test_empty_geometry_collection_round_trip(self):
        data = shapely_to_yaml(GeometryCollection())
        assert data == {"geometrycollection": None}
        assert yaml_to_shapely(data).is_empty

    def test_legacy_empty_polygon_is_read_as_empty(self):
        restored = yaml_to_shapely({"polygon": {"exterior": [], "interiors": []}})
        assert restored.is_empty

    def test_polygon_with_missing_interiors_key_is_read_as_no_holes(self):
        with_key = yaml_to_shapely({"polygon": {"exterior": [], "interiors": []}})
        without_key = yaml_to_shapely({"polygon": {"exterior": []}})
        assert without_key.equals(with_key)

    def test_empty_dict_is_read_as_empty_geometry(self):
        assert yaml_to_shapely({}).is_empty

    def test_multi_key_dict_is_read_as_empty_geometry(self):
        assert yaml_to_shapely({"polygon": {}, "multipolygon": []}).is_empty

    def test_unknown_type_key_is_read_as_empty_geometry(self):
        assert yaml_to_shapely({"triangle": None}).is_empty

    def test_unsupported_shapely_type_serialises_to_empty_geometry_collection(self):
        assert shapely_to_yaml(Point(0, 0)) == {"geometrycollection": None}

    def test_multipolygon_skips_empty_polygons(self):
        empty_polygon = shapely_to_yaml(Polygon())
        real_polygon = shapely_to_yaml(_square())
        restored = yaml_to_shapely({"multipolygon": [empty_polygon, real_polygon]})
        assert restored.equals(_square())

    def test_polygon_without_exterior_key_is_read_as_empty_geometry(self):
        assert yaml_to_shapely({"polygon": {}}).is_empty

    def test_multipolygon_with_non_list_value_is_read_as_empty_geometry(self):
        assert yaml_to_shapely({"multipolygon": "bad"}).is_empty

    def test_non_list_exterior_is_read_as_empty_geometry(self):
        assert yaml_to_shapely({"polygon": {"exterior": "bad"}}).is_empty

    def test_invalid_point_value_is_read_as_empty_geometry(self):
        restored = yaml_to_shapely(
            {"polygon": {"exterior": [{"x": None, "y": 1.0}], "interiors": []}}
        )
        assert restored.is_empty

    def test_point_missing_coordinate_key_raises(self):
        with pytest.raises(KeyError):
            yaml_to_shapely(
                {"polygon": {"exterior": [{"x": 1.0}], "interiors": []}}
            )


class TestScanZoneSettings:
    def test_zone_settings_shape(self):
        zone = ScanZone(id=4, name="Pads", color=QColor("#ff0000"), enabled=False)
        zone.add(_square())
        data = zone.settings
        assert data["id"] == 4
        assert data["name"] == "Pads"
        assert data["color"] == "#ff0000"
        assert data["enabled"] is False
        assert "polygon" in data["geometry"]

    def test_zone_from_settings_round_trip(self):
        zone = ScanZone(id=4, name="Pads", color=QColor("#ff0000"), enabled=False)
        zone.add(_square())
        restored = ScanZone.from_settings(zone.settings, id=4)
        assert restored.id == 4
        assert restored.name == "Pads"
        assert restored.color == QColor("#ff0000")
        assert restored.enabled is False
        assert restored.geometry.equals(zone.geometry)

    def test_zone_from_settings_fills_missing_fields(self):
        restored = ScanZone.from_settings({}, id=2)
        assert restored.id == 2
        assert restored.name == "Zone 2"
        assert restored.color == default_zone_color(2)
        assert restored.enabled is True
        assert restored.geometry.is_empty

    def test_zone_from_settings_uses_caller_id_not_payload_id(self):
        restored = ScanZone.from_settings({"id": 99, "name": "A"}, id=7)
        assert restored.id == 7
        assert restored.name == "A"

    def test_zone_settings_drops_color_alpha(self):
        zone = ScanZone(id=1, name="Pads", color=parse_color("#ff000080", QColor("#000000")))
        data = zone.settings
        assert data["color"] == "#ff0000"
        restored = ScanZone.from_settings(data, id=1)
        assert restored.color == QColor("#ff0000")
        assert restored.color.alpha() == 255

    def test_zone_from_settings_collapses_ops_to_add_only(self):
        zone = ScanZone(id=1, name="Pads")
        zone.add(_square(size=2.0))
        zone.remove(_square(size=1.0))
        restored = ScanZone.from_settings(zone.settings, id=1)
        assert restored.geometry.equals(zone.geometry)
        assert restored.ops
        assert all(is_add for _, is_add in restored.ops)

    def test_zone_from_settings_propagates_malformed_geometry(self):
        with pytest.raises(KeyError):
            ScanZone.from_settings(
                {"geometry": {"polygon": {"exterior": [{"x": 1}], "interiors": []}}},
                id=1,
            )


class TestScansInstrumentFlattening:
    def test_empty_model_has_no_zones_and_empty_generator(self, scans):
        assert scans.zones == {}
        assert scans.active_zone is None
        assert scans.flattened.is_empty
        assert scans.is_empty()

    def test_enabled_zones_are_unioned(self, scans):
        scans.add_zone(geometry=_square())
        scans.add_zone(geometry=_square(x=5.0))
        assert scans.flattened.area == pytest.approx(2.0)
        assert not scans.is_empty()

    def test_overlapping_zones_do_not_double_count(self, scans):
        scans.add_zone(geometry=_square(size=2.0))
        scans.add_zone(geometry=_square(size=2.0))
        assert scans.flattened.area == pytest.approx(4.0)

    def test_disabled_zone_is_excluded(self, scans):
        scans.add_zone(geometry=_square())
        second = scans.add_zone(geometry=_square(x=5.0))
        scans.update_zone_params(second.id, enabled=False)
        assert scans.flattened.area == pytest.approx(1.0)

    def test_reenabling_a_zone_brings_it_back(self, scans):
        zone = scans.add_zone(geometry=_square())
        scans.update_zone_params(zone.id, enabled=False)
        assert scans.flattened.is_empty
        scans.update_zone_params(zone.id, enabled=True)
        assert scans.flattened.area == pytest.approx(1.0)

    def test_generator_follows_the_flattened_union(self, scans):
        zone = scans.add_zone(geometry=_square())
        assert not scans.scan_path_generator.is_empty()
        scans.update_zone_params(zone.id, enabled=False)
        assert scans.scan_path_generator.is_empty()

    def test_next_point_lands_inside_an_enabled_zone(self, scans):
        scans.add_zone(geometry=_square())
        point = scans.next_point()
        assert point is not None
        assert _square().buffer(1e-9).contains(Point(*point))

    def test_next_point_returns_none_when_all_zones_disabled(self, scans):
        zone = scans.add_zone(geometry=_square())
        scans.update_zone_params(zone.id, enabled=False)
        assert scans.next_point() is None


class TestScansInstrumentDefaults:
    def test_created_zones_get_incrementing_ids_names_and_colors(self, scans):
        first = scans.add_zone()
        second = scans.add_zone()
        assert [z.name for z in scans.zones.values()] == ["Zone 1", "Zone 2"]
        assert first.id == 1
        assert second.id == 2
        assert first.color == default_zone_color(1)
        assert second.color == default_zone_color(2)

    def test_explicit_values_win(self, scans):
        zone = scans.add_zone(name="Pads", color="#123456", enabled=False)
        assert zone.name == "Pads"
        assert zone.color == QColor("#123456")
        assert zone.enabled is False

    def test_creating_a_zone_does_not_select_it(self, scans):
        scans.add_zone()
        scans.add_zone()
        assert scans.active_zone is None

    def test_duplicate_id_is_rejected(self, scans):
        scans.add_zone(id=5)
        with pytest.raises(ValueError):
            scans.add_zone(id=5)

    def test_deleting_then_adding_allocates_the_next_id(self, scans):
        scans.add_zone()
        scans.add_zone()
        scans.add_zone()
        scans.remove_zone(2)
        scans.add_zone()
        names = [z.name for z in scans.zones.values()]
        assert names == ["Zone 1", "Zone 3", "Zone 4"]
        assert set(scans.zones) == {1, 3, 4}


class TestScansInstrumentDrawing:
    def test_add_targets_the_active_zone_only(self, scans):
        first = scans.add_zone()
        second = scans.add_zone()
        scans.active_zone = second
        scans.add(_square())
        assert first.geometry.is_empty
        assert second.geometry.area == pytest.approx(1.0)

    def test_remove_targets_the_active_zone_only(self, scans):
        first = scans.add_zone(geometry=_square(size=2.0))
        second = scans.add_zone(geometry=_square(size=2.0))
        scans.active_zone = second
        scans.remove(_square(size=1.0))
        assert first.geometry.area == pytest.approx(4.0)
        assert second.geometry.area == pytest.approx(3.0)

    def test_drawing_on_an_empty_model_creates_zone_1(self, scans):
        scans.add(_square())
        assert list(scans.zones) == [1]
        assert scans.active_zone is scans.zones[1]
        assert scans.flattened.area == pytest.approx(1.0)

    def test_add_rejects_an_invalid_polygon_without_creating_a_zone(self, scans):
        seen: list[object] = []
        scans.zone_changed.connect(lambda i: seen.append(("zone", i)))
        scans.path_changed.connect(lambda: seen.append("path"))
        scans.add(Polygon())
        assert scans.zones == {}
        assert seen == []

    def test_remove_rejects_an_invalid_polygon_without_creating_a_zone(self, scans):
        seen: list[object] = []
        scans.zone_changed.connect(lambda i: seen.append(("zone", i)))
        scans.path_changed.connect(lambda: seen.append("path"))
        scans.remove(Polygon())
        assert scans.zones == {}
        assert seen == []

    def test_remove_on_empty_model_does_not_create_a_zone(self, scans):
        scans.remove(_square())
        assert scans.zones == {}
        assert scans.active_zone is None


class TestScansInstrumentIndexing:
    def test_zone_rejects_unknown_ids(self, scans):
        scans.add_zone()
        with pytest.raises(KeyError):
            scans.zone(2)
        with pytest.raises(KeyError):
            scans.zone(0)

    def test_update_and_remove_reject_unknown_ids(self, scans):
        with pytest.raises(KeyError):
            scans.update_zone_params(1, name="x")
        with pytest.raises(KeyError):
            scans.remove_zone(1)

    def test_removing_a_non_active_zone_keeps_the_active_one(self, scans):
        first = scans.add_zone()
        scans.add_zone()
        third = scans.add_zone()
        scans.active_zone = third
        scans.remove_zone(first)
        assert scans.active_zone is third
        assert set(scans.zones) == {2, 3}

    def test_removing_the_active_zone_clears_the_selection(self, scans):
        scans.add_zone()
        scans.add_zone()
        third = scans.add_zone()
        scans.active_zone = third
        scans.remove_zone(third)
        assert scans.active_zone is None
        assert set(scans.zones) == {1, 2}

    def test_removing_the_last_zone_leaves_an_empty_model(self, scans):
        zone = scans.add_zone(geometry=_square())
        scans.active_zone = zone
        scans.remove_zone(zone)
        assert scans.zones == {}
        assert scans.active_zone is None
        assert scans.flattened.is_empty

    def test_clear_removes_everything(self, scans):
        scans.add_zone(geometry=_square())
        second = scans.add_zone(geometry=_square(x=5.0))
        scans.active_zone = second
        scans.clear()
        assert scans.zones == {}
        assert scans.active_zone is None
        assert scans.scan_path_generator.is_empty()


class TestScansInstrumentSignals:
    def test_geometry_changes_emit_zone_and_path(self, scans):
        seen: list[object] = []
        scans.zone_changed.connect(lambda i: seen.append(("zone", i)))
        scans.path_changed.connect(lambda: seen.append("path"))
        zone = scans.add_zone(geometry=_square())
        assert ("zone", zone.id) in seen
        assert "path" in seen

    def test_renaming_refreshes_the_path(self, scans):
        zone = scans.add_zone(geometry=_square())
        seen: list[object] = []
        scans.zone_changed.connect(lambda i: seen.append(("zone", i)))
        scans.path_changed.connect(lambda: seen.append("path"))
        scans.update_zone_params(zone.id, name="Pads", color="#ff0000")
        assert "path" in seen
        assert ("zone", zone.id) in seen

    def test_toggling_enabled_regenerates_the_path(self, scans):
        zone = scans.add_zone(geometry=_square())
        seen: list[str] = []
        scans.path_changed.connect(lambda: seen.append("path"))
        scans.update_zone_params(zone.id, enabled=False)
        assert seen == ["path"]

    def test_setting_active_zone_emits_its_id(self, scans):
        first = scans.add_zone()
        scans.add_zone()
        seen: list[int] = []
        scans.active_zone_changed.connect(lambda i: seen.append(i))
        scans.active_zone = first
        assert seen == [first.id]
        scans.active_zone = None
        assert seen == [first.id, -1]


class TestScansInstrumentPathAppearance:
    def test_density_defaults_and_updates_the_generator(self, scans):
        assert scans.density == 100
        seen: list[str] = []
        scans.path_changed.connect(lambda: seen.append("path"))
        scans.density = 50
        assert scans.density == 50
        assert scans.scan_path_generator.density == 50
        assert seen == ["path"]

    def test_density_rejects_invalid_values(self, scans):
        with pytest.raises(ValueError):
            scans.density = 0

    def test_path_color_default_and_setter_emits_path_changed(self, scans):
        assert scans.path_color == QColor(100, 255, 0)
        seen: list[str] = []
        scans.path_changed.connect(lambda: seen.append("path"))
        scans.path_color = QColor("#ff0000")
        assert scans.path_color == QColor("#ff0000")
        assert seen == ["path"]

    def test_point_diameter_default_and_setter_emits_path_changed(self, scans):
        assert scans.point_diameter == pytest.approx(10.0)
        seen: list[str] = []
        scans.path_changed.connect(lambda: seen.append("path"))
        scans.point_diameter = 25.0
        assert scans.point_diameter == pytest.approx(25.0)
        assert seen == ["path"]


class TestScansInstrumentSettings:
    def test_settings_round_trip(self, scans):
        a = scans.add_zone(name="A", color="#ff0000", geometry=_square())
        scans.add_zone(
            name="B", color="#0000ff", enabled=False, geometry=_square(x=5.0)
        )
        scans.active_zone = a
        scans.density = 42
        data = scans.settings

        restored = ScansInstrument({})
        restored.settings = data
        assert [z.name for z in restored.zones.values()] == ["A", "B"]
        assert [z.enabled for z in restored.zones.values()] == [True, False]
        assert restored.zones[a.id].color == QColor("#ff0000")
        assert restored.active_zone is not None
        assert restored.active_zone.id == a.id
        assert restored.density == 42
        assert restored.flattened.area == pytest.approx(1.0)

    def test_settings_output_includes_flattened_geometry(self, scans):
        scans.add_zone(geometry=_square())
        scans.add_zone(geometry=_square(x=5.0), enabled=False)
        data = scans.settings
        flattened = yaml_to_shapely(data["geometry"])
        assert flattened.area == pytest.approx(1.0)

    def test_geometry_key_is_ignored_on_load(self, scans):
        scans.settings = {
            "zones": [{"id": 1, "name": "Only", "geometry": shapely_to_yaml(_square())}],
            "geometry": shapely_to_yaml(_square(size=9.0)),
        }
        assert [z.name for z in scans.zones.values()] == ["Only"]
        assert scans.flattened.area == pytest.approx(1.0)

    def test_unknown_active_id_clears_the_selection(self, scans):
        scans.settings = {"zones": [{"id": 1, "name": "A"}], "active": 5}
        assert scans.active_zone is None
        assert 1 in scans.zones

    def test_invalid_density_is_ignored(self, scans):
        before = scans.density
        scans.settings = {"density": 0, "zones": []}
        assert scans.density == before

    def test_payload_without_zones_leaves_existing_zones(self, scans):
        scans.add_zone(geometry=_square())
        scans.settings = {"density": 50}
        assert len(scans.zones) == 1
        assert scans.density == 50

    def test_malformed_zone_entry_is_skipped_without_raising(self, scans):
        scans.settings = {
            "density": 77,
            "zones": [
                {"id": 1, "name": "Good", "geometry": shapely_to_yaml(_square())},
                {
                    "id": 2,
                    "name": "Bad",
                    "geometry": {"polygon": {"exterior": [{"x": 1}], "interiors": []}},
                },
            ],
        }
        assert [z.name for z in scans.zones.values()] == ["Good"]
        assert scans.density == 77

    def test_duplicate_ids_in_payload_are_renumbered(self, scans):
        scans.settings = {
            "zones": [
                {"id": 1, "name": "A"},
                {"id": 1, "name": "B"},
            ]
        }
        assert [z.name for z in scans.zones.values()] == ["A", "B"]
        assert set(scans.zones) == {1, 2}


class TestScanGeometryPathDisplay:
    def test_path_color_change_updates_view(self, qapp, scans):
        from PyQt6.QtWidgets import QGraphicsScene

        from laserstudio.widgets.scangeometry import ScanGeometry

        scene = QGraphicsScene()
        view = ScanGeometry(scans)
        scene.addItem(view)

        red = QColor("#ff0000")
        scans.path_color = red
        assert view._ScanGeometry__scan_path.color == red
