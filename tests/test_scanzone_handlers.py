"""Unit tests for the scan zone REST handlers on ``LaserStudio``.

These exercise ``LaserStudio.handle_scan_zones`` / ``handle_add_scan_zone`` /
``handle_update_scan_zone`` / ``handle_delete_scan_zone`` directly -- the same
methods ``RestServer.run`` marshals to across the GUI-thread boundary --
without going through HTTP. ``tests/test_lsapi_*.py`` need a live server on
port 4444, so they cannot cover this layer.

Building a full ``LaserStudio`` from ``config.dummy.example.yaml`` works, but
it pulls in the whole instrument/camera stack (noisy OpenCV/PDM
hardware-probe warnings, config parsing, ~1s per instance), none of which the
scan zone handlers touch. Instead, each test gets a real ``LaserStudio``
instance built with ``LaserStudio.__new__`` -- bypassing ``__init__`` -- and
given just the ``viewer.scan_zones`` attribute the handlers under test
actually read. Because the object is still a true instance of ``LaserStudio``
(not a stand-in class), the private, name-mangled helpers the handlers call
(``__check_scan_zone_index``, ``__check_scan_zone_color``,
``__check_scan_zone_geometry``, ...) resolve normally through the class.
"""

from __future__ import annotations

import os

# Must be set before QApplication is constructed. ``setdefault`` lets a
# caller that already exported QT_QPA_PLATFORM (e.g. the CI/dev harness)
# keep their own value.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QApplication

from laserstudio.laserstudio import LaserStudio
from laserstudio.restserver.errors import InvalidParameterError, ScanZoneNotFoundError
from laserstudio.utils.scanzones import ScanZones

_SQUARE = {
    "polygon": {
        "exterior": [
            {"x": 0.0, "y": 0.0},
            {"x": 10.0, "y": 0.0},
            {"x": 10.0, "y": 10.0},
            {"x": 0.0, "y": 10.0},
        ],
        "interiors": [],
    }
}

_EMPTY_GEOMETRY = {"multipolygon": []}


@pytest.fixture(scope="module")
def qapp():
    """A single QApplication for the whole module."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def ls(qapp):
    """A ``LaserStudio`` with just enough state for the zone handlers.

    ``__init__`` builds the whole GUI/instrument stack, which these tests
    don't need and don't want the noise/cost of, so it is bypassed via
    ``__new__``. Only ``viewer.scan_zones`` -- the sole attribute the zone
    handlers touch -- is attached.
    """
    obj = LaserStudio.__new__(LaserStudio)
    obj.viewer = SimpleNamespace(scan_zones=ScanZones())
    return obj


class TestRoundTrip:
    def test_add_update_delete_round_trip(self, ls):
        added = ls.handle_add_scan_zone(name="A", color="#ff0000", geometry=_SQUARE)
        assert added["index"] == 0
        assert added["zone"]["name"] == "A"
        assert added["zone"]["color"] == "#ff0000"
        assert added["zone"]["geometry"] != _EMPTY_GEOMETRY

        listed = ls.handle_scan_zones()
        assert [z["name"] for z in listed["zones"]] == ["A"]
        assert listed["active"] == 0

        # A partial update (name only) must leave color and geometry alone.
        updated = ls.handle_update_scan_zone(0, name="B")
        assert updated["index"] == 0
        assert updated["zone"]["name"] == "B"
        assert updated["zone"]["color"] == "#ff0000"
        assert updated["zone"]["geometry"] == added["zone"]["geometry"]

        deleted = ls.handle_delete_scan_zone(0)
        assert deleted["zones"] == []
        assert deleted["active"] == 0


class TestIndexBoundaries:
    def test_update_out_of_range_reports_available_count(self, ls):
        ls.handle_add_scan_zone(name="A")
        ls.handle_add_scan_zone(name="B")
        with pytest.raises(ScanZoneNotFoundError) as excinfo:
            ls.handle_update_scan_zone(99, name="x")
        assert excinfo.value.details["available"] == 2
        # The failed call must not have mutated anything.
        assert [z["name"] for z in ls.handle_scan_zones()["zones"]] == ["A", "B"]

    def test_delete_out_of_range_reports_available_count(self, ls):
        ls.handle_add_scan_zone(name="A")
        with pytest.raises(ScanZoneNotFoundError) as excinfo:
            ls.handle_delete_scan_zone(99)
        assert excinfo.value.details["available"] == 1
        assert [z["name"] for z in ls.handle_scan_zones()["zones"]] == ["A"]

    def test_empty_model_raises_on_index_zero(self, ls):
        with pytest.raises(ScanZoneNotFoundError) as excinfo:
            ls.handle_update_scan_zone(0, name="x")
        assert excinfo.value.details["available"] == 0
        with pytest.raises(ScanZoneNotFoundError) as excinfo2:
            ls.handle_delete_scan_zone(0)
        assert excinfo2.value.details["available"] == 0


class TestGeometryValidationRegression:
    """Fix 1: a malformed geometry must be rejected up front, not crash the
    server with a bare 500 nor be silently swallowed into an empty zone."""

    def test_non_dict_point_element_is_rejected(self, ls):
        with pytest.raises(InvalidParameterError):
            ls.handle_add_scan_zone(geometry={"polygon": {"exterior": [1, 2, 3]}})
        # Rejected before any mutation: no zone was created.
        assert ls.handle_scan_zones()["zones"] == []

    def test_wrong_keys_are_rejected_rather_than_silently_empty(self, ls):
        with pytest.raises(InvalidParameterError):
            ls.handle_add_scan_zone(geometry={"polygon": {"nope": 1}})
        assert ls.handle_scan_zones()["zones"] == []

    def test_valid_geometry_still_succeeds(self, ls):
        added = ls.handle_add_scan_zone(geometry=_SQUARE)
        assert added["zone"]["geometry"] != _EMPTY_GEOMETRY

    def test_update_also_validates_geometry(self, ls):
        ls.handle_add_scan_zone(name="A", geometry=_SQUARE)
        with pytest.raises(InvalidParameterError):
            ls.handle_update_scan_zone(0, geometry={"polygon": {"exterior": [1]}})
        # The zone's original geometry must be untouched by the failed call.
        assert ls.handle_scan_zones()["zones"][0]["geometry"] != _EMPTY_GEOMETRY


class TestColorValidationRegression:
    """Fix 2: an invalid color must be rejected, not silently replaced by
    the palette default."""

    def test_invalid_color_is_rejected(self, ls):
        with pytest.raises(InvalidParameterError):
            ls.handle_add_scan_zone(color="zzz")
        assert ls.handle_scan_zones()["zones"] == []

    def test_valid_rrggbbaa_color_still_succeeds(self, ls):
        added = ls.handle_add_scan_zone(color="#ff0000cc")
        # Alpha is deliberately not persisted (see ScanZone.settings).
        assert added["zone"]["color"] == "#ff0000"

    def test_update_also_validates_color(self, ls):
        ls.handle_add_scan_zone(name="A", color="#ff0000")
        with pytest.raises(InvalidParameterError):
            ls.handle_update_scan_zone(0, color="not-a-color")
        assert ls.handle_scan_zones()["zones"][0]["color"] == "#ff0000"
