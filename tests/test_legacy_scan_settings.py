"""Backwards compatibility of scan settings written by pre-zones Laser Studio.

Before scan zones existed, ``ScanGeometry.settings`` produced
``{"density": int, "geometry": <serialised shapely>}`` — a single, unnamed
geometry. Those files are sitting in users' working directories, and scripts
still ``PUT`` that same shape at ``/scangeometry``. Loading one must reproduce
exactly the geometry the old version had, as one enabled zone.

The payloads below were checked against the output of the real pre-zones
``ScanGeometry`` (commit 142a37f), run in a worktree: each one is
geometrically equal to what that version actually wrote, and carries the
same keys and density. They are written out literally here rather than
captured verbatim, so ring winding and vertex order may differ from
shapely's own output — the comparison that matters, and the one that was
verified, is geometric equality.
"""

from __future__ import annotations

import pytest

from laserstudio.utils.scanzones import ScanZones, yaml_to_shapely


def _ring(points: list[tuple[float, float]]) -> list[dict[str, float]]:
    return [{"x": x, "y": y} for x, y in points]


def _rect(x: float, y: float, w: float, h: float) -> dict:
    return {
        "polygon": {
            "exterior": _ring(
                [(x, y), (x, y + h), (x + w, y + h), (x + w, y), (x, y)]
            ),
            "interiors": [],
        }
    }


# Captured from the pre-zones implementation; see the module docstring.
LEGACY_PAYLOADS: dict[str, tuple[dict, float]] = {
    "single_rect": ({"density": 100, "geometry": _rect(0, 0, 100, 100)}, 10000.0),
    "multipolygon": (
        {
            "density": 100,
            "geometry": {
                "multipolygon": [_rect(0, 0, 100, 100), _rect(300, 0, 100, 100)]
            },
        },
        20000.0,
    ),
    "rect_with_hole": (
        {
            "density": 100,
            "geometry": {
                "polygon": {
                    "exterior": _ring(
                        [(0, 0), (0, 200), (200, 200), (200, 0), (0, 0)]
                    ),
                    "interiors": [
                        _ring([(50, 50), (150, 50), (150, 150), (50, 150), (50, 50)])
                    ],
                }
            },
        },
        30000.0,
    ),
    "custom_density": ({"density": 250, "geometry": _rect(0, 0, 60, 60)}, 3600.0),
    # What LaserStudio.EMPTY_SCAN_GEOMETRY has always produced.
    "empty": (
        {"density": 100, "geometry": {"polygon": {"exterior": [], "interiors": []}}},
        0.0,
    ),
}


@pytest.mark.parametrize("name", sorted(LEGACY_PAYLOADS))
def test_legacy_payload_loads_with_the_same_geometry(name: str):
    payload, expected_area = LEGACY_PAYLOADS[name]
    zones = ScanZones()
    zones.settings = payload

    assert zones.flattened.area == pytest.approx(expected_area)
    assert zones.flattened.equals(yaml_to_shapely(payload["geometry"]))
    assert zones.density == payload["density"]


@pytest.mark.parametrize("name", sorted(LEGACY_PAYLOADS))
def test_legacy_payload_becomes_one_enabled_zone(name: str):
    payload, _ = LEGACY_PAYLOADS[name]
    zones = ScanZones()
    zones.settings = payload

    assert len(zones.zones) == 1
    assert zones.zones[0].name == "Zone 1"
    assert zones.zones[0].enabled is True
    assert zones.active_index == 0


def test_legacy_payload_still_generates_points():
    payload, _ = LEGACY_PAYLOADS["single_rect"]
    zones = ScanZones()
    zones.settings = payload
    assert zones.next_point() is not None


def test_a_bare_geometry_dict_without_the_wrapper_is_accepted():
    """Some callers PUT the serialised geometry itself, with no outer key."""
    zones = ScanZones()
    zones.settings = _rect(0, 0, 100, 100)
    assert zones.flattened.area == pytest.approx(10000.0)
    assert len(zones.zones) == 1


def test_new_settings_stay_readable_by_an_older_version():
    """The output keeps the keys a pre-zones Laser Studio reads.

    An older version looks for ``geometry``/``density`` and ignores the rest,
    so it must find the union of the *enabled* zones there — otherwise a
    downgrade, or a colleague on an older build, would scan the wrong area.
    """
    zones = ScanZones()
    zones.add_zone(name="A", geometry=yaml_to_shapely(_rect(0, 0, 100, 100)))
    zones.add_zone(name="B", geometry=yaml_to_shapely(_rect(300, 0, 100, 100)))
    zones.add_zone(
        name="Off", enabled=False, geometry=yaml_to_shapely(_rect(600, 0, 100, 100))
    )
    zones.density = 175

    settings = zones.settings
    assert settings["density"] == 175
    # Exactly the two enabled zones, not all three.
    assert yaml_to_shapely(settings["geometry"]).area == pytest.approx(20000.0)


def test_a_legacy_payload_replaces_existing_zones_rather_than_merging():
    """Loading an old file is a full restore, as it always was."""
    zones = ScanZones()
    zones.add_zone(name="Stale", geometry=yaml_to_shapely(_rect(0, 0, 500, 500)))
    payload, expected_area = LEGACY_PAYLOADS["single_rect"]
    zones.settings = payload

    assert [z.name for z in zones.zones] == ["Zone 1"]
    assert zones.flattened.area == pytest.approx(expected_area)
