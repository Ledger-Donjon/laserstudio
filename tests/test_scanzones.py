"""Unit tests for laserstudio.utils.scanzones."""

from __future__ import annotations

import pytest
from PyQt6.QtGui import QColor
from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon

from laserstudio.utils.scanzones import (
    DEFAULT_ZONE_COLORS,
    ScanZone,
    ScanZones,
    parse_color,
    shapely_to_yaml,
    yaml_to_shapely,
)


def _square(x: float = 0.0, y: float = 0.0, size: float = 1.0) -> Polygon:
    return Polygon(
        [(x, y), (x + size, y), (x + size, y + size), (x, y + size)]
    )


class TestScanZone:
    def test_new_zone_is_empty_and_enabled(self):
        zone = ScanZone("Zone 1")
        assert zone.name == "Zone 1"
        assert zone.enabled is True
        assert zone.color == DEFAULT_ZONE_COLORS[0]
        assert zone.geometry.is_empty
        assert zone.polygons == []

    def test_add_polygon_becomes_the_geometry(self):
        zone = ScanZone("Zone 1")
        assert zone.add(_square()) is True
        assert zone.geometry.area == pytest.approx(1.0)
        assert len(zone.polygons) == 1

    def test_remove_subtracts_from_the_geometry(self):
        zone = ScanZone("Zone 1")
        zone.add(_square(size=2.0))
        zone.remove(_square(size=1.0))
        assert zone.geometry.area == pytest.approx(3.0)

    def test_add_rejects_invalid_and_empty_polygons(self):
        zone = ScanZone("Zone 1")
        assert zone.add(Polygon()) is False
        # A bow-tie polygon is self-intersecting, hence invalid.
        bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])
        assert zone.add(bowtie) is False
        assert zone.geometry.is_empty

    def test_geometry_is_cached_until_invalidated(self):
        zone = ScanZone("Zone 1")
        zone.add(_square())
        first = zone.geometry
        assert zone.geometry is first
        zone.add(_square(x=5.0))
        assert zone.geometry is not first
        assert zone.geometry.area == pytest.approx(2.0)

    def test_set_polygons_replaces_the_operations(self):
        zone = ScanZone("Zone 1")
        zone.add(_square(size=3.0))
        zone.remove(_square(size=1.0))
        zone.set_polygons([_square(size=2.0)])
        assert zone.geometry.area == pytest.approx(4.0)
        assert zone.ops == [(_square(size=2.0), True)]

    def test_set_geometry_flattens_a_multipolygon(self):
        zone = ScanZone("Zone 1")
        zone.set_geometry(MultiPolygon([_square(), _square(x=5.0)]))
        assert len(zone.polygons) == 2
        assert zone.geometry.area == pytest.approx(2.0)

    def test_remove_rejects_invalid_and_empty_polygons(self):
        zone = ScanZone("Zone 1")
        zone.add(_square(size=2.0))
        assert zone.remove(Polygon()) is False
        # A bow-tie polygon is self-intersecting, hence invalid.
        bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])
        assert zone.remove(bowtie) is False
        assert zone.geometry.area == pytest.approx(4.0)

    def test_ops_constructor_parameter_seeds_the_operations(self):
        square = _square(size=2.0)
        hole = _square(size=1.0)
        zone = ScanZone("Zone 1", ops=[(square, True), (hole, False)])
        assert zone.ops == [(square, True), (hole, False)]
        assert zone.geometry.area == pytest.approx(3.0)


class TestParseColor:
    def test_hex_rgb(self):
        assert parse_color("#ff0000", QColor("#00ff00")) == QColor(255, 0, 0)

    def test_hex_rgba_alpha_is_last(self):
        color = parse_color("#ff000080", QColor("#00ff00"))
        assert (color.red(), color.green(), color.blue()) == (255, 0, 0)
        assert color.alpha() == 0x80

    def test_invalid_falls_back_to_default(self):
        default = QColor("#00ff00")
        assert parse_color("not-a-colour", default) == default
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
        # The shape LaserStudio.EMPTY_SCAN_GEOMETRY has always produced.
        restored = yaml_to_shapely({"polygon": {"exterior": [], "interiors": []}})
        assert restored.is_empty

    def test_polygon_with_missing_interiors_key_is_read_as_no_holes(self):
        # "interiors" absent entirely must behave the same as an empty list.
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
        restored = yaml_to_shapely(
            {"multipolygon": [empty_polygon, real_polygon]}
        )
        assert restored.equals(_square())

    def test_polygon_without_exterior_key_is_read_as_empty_geometry(self):
        assert yaml_to_shapely({"polygon": {}}).is_empty

    def test_multipolygon_with_non_list_value_is_read_as_empty_geometry(self):
        assert yaml_to_shapely({"multipolygon": "bad"}).is_empty


class TestScanZonesFlattening:
    def test_empty_model_has_no_zones_and_empty_generator(self):
        zones = ScanZones()
        assert zones.zones == []
        assert zones.active_zone is None
        assert zones.flattened.is_empty
        assert zones.is_empty()

    def test_enabled_zones_are_unioned(self):
        zones = ScanZones()
        zones.add_zone(geometry=_square())
        zones.add_zone(geometry=_square(x=5.0))
        assert zones.flattened.area == pytest.approx(2.0)
        assert not zones.is_empty()

    def test_overlapping_zones_do_not_double_count(self):
        zones = ScanZones()
        zones.add_zone(geometry=_square(size=2.0))
        zones.add_zone(geometry=_square(size=2.0))
        assert zones.flattened.area == pytest.approx(4.0)

    def test_disabled_zone_is_excluded(self):
        zones = ScanZones()
        zones.add_zone(geometry=_square())
        index = zones.add_zone(geometry=_square(x=5.0))
        zones.update_zone(index, enabled=False)
        assert zones.flattened.area == pytest.approx(1.0)

    def test_reenabling_a_zone_brings_it_back(self):
        zones = ScanZones()
        index = zones.add_zone(geometry=_square())
        zones.update_zone(index, enabled=False)
        assert zones.flattened.is_empty
        zones.update_zone(index, enabled=True)
        assert zones.flattened.area == pytest.approx(1.0)

    def test_generator_follows_the_flattened_union(self):
        zones = ScanZones()
        index = zones.add_zone(geometry=_square())
        assert not zones.scan_path_generator.is_empty()
        zones.update_zone(index, enabled=False)
        assert zones.scan_path_generator.is_empty()

    def test_next_point_lands_inside_an_enabled_zone(self):
        zones = ScanZones()
        zones.add_zone(geometry=_square())
        point = zones.next_point()
        assert point is not None
        assert _square().buffer(1e-9).contains(Point(*point))

    def test_next_point_returns_none_when_all_zones_disabled(self):
        zones = ScanZones()
        index = zones.add_zone(geometry=_square())
        zones.update_zone(index, enabled=False)
        assert zones.next_point() is None


class TestScanZonesDefaults:
    def test_created_zones_get_incrementing_names_and_colours(self):
        zones = ScanZones()
        zones.add_zone()
        zones.add_zone()
        assert [z.name for z in zones.zones] == ["Zone 1", "Zone 2"]
        assert zones.zones[0].color == DEFAULT_ZONE_COLORS[0]
        assert zones.zones[1].color == DEFAULT_ZONE_COLORS[1]

    def test_explicit_values_win(self):
        zones = ScanZones()
        zones.add_zone(name="Pads", color="#123456", enabled=False)
        zone = zones.zones[0]
        assert zone.name == "Pads"
        assert zone.color == QColor("#123456")
        assert zone.enabled is False

    def test_creating_a_zone_does_not_change_the_active_index(self):
        zones = ScanZones()
        zones.add_zone()
        zones.add_zone()
        assert zones.active_index == 0

    def test_deleting_then_adding_does_not_reuse_a_live_name(self):
        zones = ScanZones()
        zones.add_zone()
        zones.add_zone()
        zones.add_zone()
        zones.remove_zone(1)
        zones.add_zone()
        names = [z.name for z in zones.zones]
        assert names == ["Zone 1", "Zone 3", "Zone 4"]
        assert len(names) == len(set(names))


class TestScanZonesDrawing:
    def test_add_targets_the_active_zone_only(self):
        zones = ScanZones()
        zones.add_zone()
        zones.add_zone()
        zones.active_index = 1
        zones.add(_square())
        assert zones.zones[0].geometry.is_empty
        assert zones.zones[1].geometry.area == pytest.approx(1.0)

    def test_remove_targets_the_active_zone_only(self):
        zones = ScanZones()
        zones.add_zone(geometry=_square(size=2.0))
        zones.add_zone(geometry=_square(size=2.0))
        zones.active_index = 1
        zones.remove(_square(size=1.0))
        assert zones.zones[0].geometry.area == pytest.approx(4.0)
        assert zones.zones[1].geometry.area == pytest.approx(3.0)

    def test_drawing_on_an_empty_model_creates_zone_1(self):
        zones = ScanZones()
        zones.add(_square())
        assert [z.name for z in zones.zones] == ["Zone 1"]
        assert zones.active_index == 0
        assert zones.flattened.area == pytest.approx(1.0)

    def test_active_index_is_clamped(self):
        zones = ScanZones()
        zones.add_zone()
        zones.active_index = 7
        assert zones.active_index == 0
        zones.active_index = -3
        assert zones.active_index == 0

    def test_add_rejects_an_invalid_polygon_without_creating_a_zone(self):
        zones = ScanZones()
        seen: list[str] = []
        zones.changed.connect(lambda: seen.append("changed"))
        zones.path_changed.connect(lambda: seen.append("path"))
        zones.add(Polygon())
        assert zones.zones == []
        assert seen == []

    def test_remove_rejects_an_invalid_polygon_without_creating_a_zone(self):
        zones = ScanZones()
        seen: list[str] = []
        zones.changed.connect(lambda: seen.append("changed"))
        zones.path_changed.connect(lambda: seen.append("path"))
        zones.remove(Polygon())
        assert zones.zones == []
        assert seen == []


class TestScanZonesIndexing:
    def test_zone_rejects_out_of_range_indices(self):
        zones = ScanZones()
        zones.add_zone()
        with pytest.raises(IndexError):
            zones.zone(1)
        with pytest.raises(IndexError):
            zones.zone(-1)

    def test_update_and_remove_reject_out_of_range_indices(self):
        zones = ScanZones()
        with pytest.raises(IndexError):
            zones.update_zone(0, name="x")
        with pytest.raises(IndexError):
            zones.remove_zone(0)

    def test_removing_a_zone_before_the_active_one_keeps_it_active(self):
        zones = ScanZones()
        for _ in range(3):
            zones.add_zone()
        zones.active_index = 2
        zones.remove_zone(0)
        assert zones.active_index == 1
        assert zones.active_zone is not None
        assert zones.active_zone.name == "Zone 3"

    def test_removing_the_active_zone_selects_the_previous_one(self):
        zones = ScanZones()
        for _ in range(3):
            zones.add_zone()
        zones.active_index = 2
        zones.remove_zone(2)
        assert zones.active_index == 1

    def test_removing_the_first_active_zone_keeps_index_zero(self):
        zones = ScanZones()
        for _ in range(2):
            zones.add_zone()
        zones.remove_zone(0)
        assert zones.active_index == 0
        assert zones.active_zone is not None
        assert zones.active_zone.name == "Zone 2"

    def test_removing_the_last_zone_leaves_an_empty_model(self):
        zones = ScanZones()
        zones.add_zone(geometry=_square())
        zones.remove_zone(0)
        assert zones.zones == []
        assert zones.active_index == 0
        assert zones.flattened.is_empty

    def test_clear_removes_everything(self):
        zones = ScanZones()
        zones.add_zone(geometry=_square())
        zones.add_zone(geometry=_square(x=5.0))
        zones.active_index = 1
        zones.clear()
        assert zones.zones == []
        assert zones.active_index == 0
        assert zones.scan_path_generator.is_empty()


class TestScanZonesSignals:
    def test_geometry_changes_emit_both_signals(self):
        zones = ScanZones()
        seen: list[str] = []
        zones.changed.connect(lambda: seen.append("changed"))
        zones.path_changed.connect(lambda: seen.append("path"))
        zones.add_zone(geometry=_square())
        assert "changed" in seen
        assert "path" in seen

    def test_renaming_does_not_regenerate_the_path(self):
        zones = ScanZones()
        index = zones.add_zone(geometry=_square())
        seen: list[str] = []
        zones.changed.connect(lambda: seen.append("changed"))
        zones.path_changed.connect(lambda: seen.append("path"))
        zones.update_zone(index, name="Pads", color="#ff0000")
        assert seen == ["changed"]

    def test_toggling_enabled_regenerates_the_path(self):
        zones = ScanZones()
        index = zones.add_zone(geometry=_square())
        seen: list[str] = []
        zones.path_changed.connect(lambda: seen.append("path"))
        zones.update_zone(index, enabled=False)
        assert seen == ["path"]

    def test_setting_the_same_active_index_emits_nothing(self):
        zones = ScanZones()
        zones.add_zone()
        zones.add_zone()
        zones.active_index = 1
        seen: list[str] = []
        zones.changed.connect(lambda: seen.append("changed"))
        zones.active_index = 1
        assert seen == []


class TestScanZonesPathAppearance:
    def test_density_defaults_and_updates_the_generator(self):
        zones = ScanZones()
        assert zones.density == 100
        seen: list[str] = []
        zones.path_changed.connect(lambda: seen.append("path"))
        zones.density = 50
        assert zones.density == 50
        assert zones.scan_path_generator.density == 50
        assert seen == ["path"]

    def test_density_rejects_invalid_values(self):
        zones = ScanZones()
        with pytest.raises(ValueError):
            zones.density = 0

    def test_path_color_default_and_setter_emits_changed(self):
        zones = ScanZones()
        assert zones.path_color == QColor(100, 255, 0)
        seen: list[str] = []
        zones.changed.connect(lambda: seen.append("changed"))
        zones.path_color = QColor("#ff0000")
        assert zones.path_color == QColor("#ff0000")
        assert seen == ["changed"]

    def test_point_diameter_default_and_setter_emits_changed(self):
        zones = ScanZones()
        assert zones.point_diameter == pytest.approx(10.0)
        seen: list[str] = []
        zones.changed.connect(lambda: seen.append("changed"))
        zones.point_diameter = 25.0
        assert zones.point_diameter == pytest.approx(25.0)
        assert seen == ["changed"]


class TestScanZoneSettings:
    def test_zone_settings_shape(self):
        zone = ScanZone("Pads", QColor("#ff0000"), enabled=False)
        zone.add(_square())
        data = zone.settings
        assert data["name"] == "Pads"
        assert data["color"] == "#ff0000"
        assert data["enabled"] is False
        assert "polygon" in data["geometry"]

    def test_zone_from_settings_round_trip(self):
        zone = ScanZone("Pads", QColor("#ff0000"), enabled=False)
        zone.add(_square())
        restored = ScanZone.from_settings(zone.settings)
        assert restored.name == "Pads"
        assert restored.color == QColor("#ff0000")
        assert restored.enabled is False
        assert restored.geometry.equals(zone.geometry)

    def test_zone_from_settings_fills_missing_fields(self):
        restored = ScanZone.from_settings({}, index=2)
        assert restored.name == "Zone 3"
        assert restored.color == DEFAULT_ZONE_COLORS[2]
        assert restored.enabled is True
        assert restored.geometry.is_empty

    def test_zone_settings_drops_colour_alpha(self):
        # Alpha is deliberately not persisted: the wire form is "#rrggbb"
        # even though parse_color accepts "#rrggbbaa" on input.
        zone = ScanZone("Pads", parse_color("#ff000080", QColor("#000000")))
        data = zone.settings
        assert data["color"] == "#ff0000"
        restored = ScanZone.from_settings(data)
        assert restored.color == QColor("#ff0000")
        assert restored.color.alpha() == 255

    def test_zone_from_settings_collapses_ops_to_add_only(self):
        # A zone drawn as add-then-subtract has a hole; settings only stores
        # the merged geometry, so the round trip keeps the shape but not the
        # operation history.
        zone = ScanZone("Pads")
        zone.add(_square(size=2.0))
        zone.remove(_square(size=1.0))
        restored = ScanZone.from_settings(zone.settings)
        assert restored.geometry.equals(zone.geometry)
        assert restored.ops
        assert all(is_add for _, is_add in restored.ops)


class TestScanZonesSettings:
    def test_settings_round_trip(self):
        zones = ScanZones()
        zones.add_zone(name="A", color="#ff0000", geometry=_square())
        zones.add_zone(name="B", color="#0000ff", enabled=False,
                       geometry=_square(x=5.0))
        zones.active_index = 1
        zones.density = 42
        data = zones.settings

        restored = ScanZones()
        restored.settings = data
        assert [z.name for z in restored.zones] == ["A", "B"]
        assert [z.enabled for z in restored.zones] == [True, False]
        assert restored.zones[0].color == QColor("#ff0000")
        assert restored.active_index == 1
        assert restored.density == 42
        assert restored.flattened.area == pytest.approx(1.0)

    def test_settings_output_includes_flattened_geometry(self):
        zones = ScanZones()
        zones.add_zone(geometry=_square())
        zones.add_zone(geometry=_square(x=5.0), enabled=False)
        data = zones.settings
        flattened = yaml_to_shapely(data["geometry"])
        assert flattened.area == pytest.approx(1.0)

    def test_legacy_single_polygon_becomes_zone_1(self):
        zones = ScanZones()
        zones.settings = {
            "density": 7,
            "geometry": shapely_to_yaml(_square(size=2.0)),
        }
        assert len(zones.zones) == 1
        assert zones.zones[0].name == "Zone 1"
        assert zones.zones[0].enabled is True
        assert zones.zones[0].color == DEFAULT_ZONE_COLORS[0]
        assert zones.flattened.area == pytest.approx(4.0)
        assert zones.density == 7

    def test_legacy_multipolygon_becomes_one_zone_with_two_polygons(self):
        zones = ScanZones()
        zones.settings = {
            "geometry": shapely_to_yaml(MultiPolygon([_square(), _square(x=5.0)]))
        }
        assert len(zones.zones) == 1
        assert len(zones.zones[0].polygons) == 2

    def test_legacy_bare_polygon_key_is_accepted(self):
        zones = ScanZones()
        zones.settings = shapely_to_yaml(_square())
        assert len(zones.zones) == 1
        assert zones.flattened.area == pytest.approx(1.0)

    def test_legacy_empty_polygon_clears_the_zones(self):
        zones = ScanZones()
        zones.add_zone(geometry=_square())
        zones.settings = {"geometry": {"polygon": {"exterior": [], "interiors": []}}}
        assert zones.flattened.is_empty

    def test_zones_key_wins_over_geometry_key(self):
        zones = ScanZones()
        zones.settings = {
            "zones": [{"name": "Only", "geometry": shapely_to_yaml(_square())}],
            "geometry": shapely_to_yaml(_square(size=9.0)),
        }
        assert [z.name for z in zones.zones] == ["Only"]
        assert zones.flattened.area == pytest.approx(1.0)

    def test_active_index_out_of_range_is_clamped(self):
        zones = ScanZones()
        zones.settings = {"zones": [{"name": "A"}], "active": 5}
        assert zones.active_index == 0

    def test_invalid_density_is_ignored(self):
        zones = ScanZones()
        before = zones.density
        zones.settings = {"density": 0, "zones": []}
        assert zones.density == before

    def test_unusable_payload_leaves_zones_untouched(self):
        zones = ScanZones()
        zones.add_zone(geometry=_square())
        zones.settings = {"density": 50}
        assert len(zones.zones) == 1
        assert zones.density == 50

    def test_malformed_zone_entry_is_skipped_without_raising(self):
        zones = ScanZones()
        zones.settings = {
            "density": 77,
            "zones": [
                {"name": "Good", "geometry": shapely_to_yaml(_square())},
                {
                    "name": "Bad",
                    "geometry": {
                        "polygon": {"exterior": [{"x": 1}], "interiors": []}
                    },
                },
            ],
        }
        assert [z.name for z in zones.zones] == ["Good"]
        assert zones.density == 77
