"""Unit tests for laserstudio.widgets.scangeometry.

These exercise the ``ScanGeometry`` view class: model-driven rendering rules
and the per-zone interactive vertex-edition machinery. Qt graphics items work
fine under the offscreen platform plugin, so no real display is needed.
"""

from __future__ import annotations

import os

# Must be set before QApplication is constructed. ``setdefault`` lets a
# caller that already exported QT_QPA_PLATFORM (e.g. the CI/dev harness)
# keep their own value.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QColorConstants
from PyQt6.QtWidgets import QApplication, QGraphicsScene
from shapely.geometry import Polygon

from laserstudio.utils.scanzones import ScanZones, default_zone_color
from laserstudio.widgets.scangeometry import ScanGeometry
from laserstudio.widgets.viewer import Viewer


def _square(x: float = 0.0, y: float = 0.0, size: float = 10.0) -> Polygon:
    return Polygon([(x, y), (x + size, y), (x + size, y + size), (x, y + size)])


@pytest.fixture(scope="module")
def qapp():
    """A single QApplication for the whole module."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def scene_and_view(qapp):
    """A fresh model, scene and view for each test.

    The scene must be kept alive for the lifetime of the test: a
    ``QGraphicsScene`` with no Python reference left can be garbage-collected
    on the C++ side, taking its child items (the view, and everything the
    view added to it) down with it and turning later access into a
    "wrapped C/C++ object has been deleted" crash.
    """
    zones = ScanZones()
    scene = QGraphicsScene()
    view = ScanGeometry(zones)
    scene.addItem(view)
    return zones, scene, view


class TestRenderingRules:
    def test_enabled_zone_solid_pen_and_translucent_brush(self, scene_and_view):
        zones, _scene, view = scene_and_view
        zones.add_zone(geometry=_square())
        items = view._ScanGeometry__scan_geometry_items.childItems()
        assert len(items) == 1
        item = items[0]
        assert item.pen().style() == Qt.PenStyle.SolidLine
        assert item.brush().style() != Qt.BrushStyle.NoBrush

    def test_disabled_non_active_zone_renders_nothing_and_has_no_handles(
        self, scene_and_view
    ):
        zones, _scene, view = scene_and_view
        zones.add_zone(geometry=_square())  # zone 0, active by default
        zones.add_zone(geometry=_square(x=20.0), enabled=False)  # zone 1
        items = view._ScanGeometry__scan_geometry_items.childItems()
        assert len(items) == 1
        # Only zone 0's 4 vertices get handles; zone 1 contributes none.
        assert len(view._ScanGeometry__vertex_handles) == 4
        assert all(h.zone_index == 0 for h in view._ScanGeometry__vertex_handles)

    def test_disabled_active_zone_is_dashed_with_no_brush(self, scene_and_view):
        zones, _scene, view = scene_and_view
        zones.add_zone(geometry=_square(), enabled=False)
        zones.active_index = 0
        items = view._ScanGeometry__scan_geometry_items.childItems()
        assert len(items) == 1
        item = items[0]
        assert item.pen().style() == Qt.PenStyle.DashLine
        assert item.brush().style() == Qt.BrushStyle.NoBrush

    def test_active_zone_outline_is_thicker_than_non_active(self, scene_and_view):
        zones, _scene, view = scene_and_view
        zones.add_zone(geometry=_square())  # zone 0, active (default index 0)
        zones.add_zone(geometry=_square(x=20.0))  # zone 1, enabled, not active
        items = view._ScanGeometry__scan_geometry_items.childItems()
        assert len(items) == 2
        widths = sorted(item.pen().width() for item in items)
        assert widths == [1, 2]


class TestDragCycle:
    def test_full_drag_moves_vertex_and_leaves_ops_add_only(self, scene_and_view):
        zones, _scene, view = scene_and_view
        zones.add_zone(geometry=_square())
        # GEOS's union (run when the zone's cached ``geometry`` is computed)
        # is free to reorder or reverse the ring, so a vertex's index among
        # the handles is not the same as its index in the input list. Locate
        # the handle by its actual on-screen position instead of assuming
        # which index corresponds to the (0, 0) corner.
        handle = next(
            h
            for h in view._ScanGeometry__vertex_handles
            if h.pos() == QPointF(0.0, 0.0)
        )
        view._begin_handle_move(handle)
        view._handle_move(handle, QPointF(-5.0, -5.0))
        view._end_handle_move()
        moved_poly = zones.zones[0].polygons[0]
        coords = list(moved_poly.exterior.coords)[:-1]
        assert any(c == pytest.approx((-5.0, -5.0)) for c in coords)
        assert not any(c == pytest.approx((0.0, 0.0)) for c in coords)
        assert zones.zones[0].geometry.area != pytest.approx(100.0)
        assert all(is_add for _, is_add in zones.zones[0].ops)


class TestRebuildHandlesRegression:
    def test_rebuild_handles_called_twice_keeps_handles(self, scene_and_view):
        """Pins the bug class fixed by the refactor: rebuilding handles while
        old handles are already attached to the scene must not lose them."""
        zones, _scene, view = scene_and_view
        zones.add_zone(geometry=_square())
        assert len(view._ScanGeometry__vertex_handles) == 4
        view._ScanGeometry__rebuild_handles()
        assert len(view._ScanGeometry__vertex_handles) == 4
        view._ScanGeometry__rebuild_handles()
        assert len(view._ScanGeometry__vertex_handles) == 4


class TestFix1ZoneIdentityDuringDrag:
    def test_removing_a_preceding_zone_mid_drag_commits_to_correct_zone(
        self, scene_and_view
    ):
        zones, _scene, view = scene_and_view
        zones.add_zone(name="A", geometry=_square())
        zones.add_zone(name="B", geometry=_square(x=20.0))
        zones.add_zone(name="C", geometry=_square(x=40.0))
        handle = next(
            h for h in view._ScanGeometry__vertex_handles if h.zone_index == 1
        )  # a vertex of B
        view._begin_handle_move(handle)
        zones.remove_zone(0)  # remove A; B is now index 0, C is now index 1
        view._handle_move(handle, QPointF(-100.0, -100.0))
        view._end_handle_move()

        assert zones.zones[0].name == "B"
        assert zones.zones[0].geometry.area != pytest.approx(100.0)
        assert zones.zones[1].name == "C"
        assert zones.zones[1].geometry.area == pytest.approx(100.0)

    def test_removing_the_edited_zone_mid_drag_keeps_others_rendered(
        self, scene_and_view
    ):
        zones, _scene, view = scene_and_view
        zones.add_zone(name="A", geometry=_square())
        zones.add_zone(name="B", geometry=_square(x=20.0))
        zones.add_zone(name="C", geometry=_square(x=40.0))
        handle = next(
            h for h in view._ScanGeometry__vertex_handles if h.zone_index == 1
        )  # a vertex of B
        view._begin_handle_move(handle)
        zones.remove_zone(1)  # remove B itself, the zone being edited
        view._handle_move(handle, QPointF(-100.0, -100.0))
        view._end_handle_move()

        assert [z.name for z in zones.zones] == ["A", "C"]
        items = view._ScanGeometry__scan_geometry_items.childItems()
        assert len(items) > 0


class TestFix2InvalidDragPreservesShape:
    def test_self_intersecting_drag_leaves_geometry_unchanged(self, scene_and_view):
        zones, _scene, view = scene_and_view
        zones.add_zone(geometry=_square())
        before_area = zones.zones[0].geometry.area
        handle = next(
            h for h in view._ScanGeometry__vertex_handles if h.handle_index == 0
        )
        view._begin_handle_move(handle)
        # Drag the (0, 0) corner far past the opposite edge: self-intersecting.
        view._handle_move(handle, QPointF(100.0, 100.0))
        view._end_handle_move()

        assert zones.zones[0].geometry.area == pytest.approx(before_area)
        assert len(zones.zones[0].polygons) > 0


class TestCursorProximity:
    def test_reveals_within_threshold_and_hides_on_none(self, scene_and_view):
        zones, _scene, view = scene_and_view
        zones.add_zone(geometry=_square())
        view.update_cursor_proximity(QPointF(0.0, 0.0), 2.0)
        visible = [h for h in view._ScanGeometry__vertex_handles if h.isVisible()]
        assert len(visible) == 1
        view.update_cursor_proximity(None, 0.0)
        assert all(not h.isVisible() for h in view._ScanGeometry__vertex_handles)

    def test_no_op_while_handles_dragging(self, scene_and_view):
        zones, _scene, view = scene_and_view
        zones.add_zone(geometry=_square())
        handle = view._ScanGeometry__vertex_handles[0]
        handle.setVisible(True)
        view._begin_handle_move(handle)  # sets __handles_dragging True
        view.update_cursor_proximity(None, 0.0)
        assert handle.isVisible() is True
        view._end_handle_move()


class TestSharedModelMultipleViews:
    """Two ``ScanGeometry`` views over one ``ScanZones`` model.

    Task 7/8 let two windows share a single model; these pin the contract
    that both views actually redraw when the shared model changes, rather
    than merely asserting on the model itself (which would pass even if a
    view had stopped listening to its signals).
    """

    @pytest.fixture
    def two_views(self, qapp):
        # Both scenes must be kept alive for the test's lifetime (see the
        # ``scene_and_view`` fixture's docstring above): an unreferenced
        # ``QGraphicsScene`` can be garbage-collected on the C++ side, taking
        # its items down with it.
        zones = ScanZones()
        scene_a = QGraphicsScene()
        view_a = ScanGeometry(zones)
        scene_a.addItem(view_a)
        scene_b = QGraphicsScene()
        view_b = ScanGeometry(zones)
        scene_b.addItem(view_b)
        return zones, view_a, view_b, scene_a, scene_b

    def test_adding_a_zone_renders_in_both_views(self, two_views):
        zones, view_a, view_b, _scene_a, _scene_b = two_views
        zones.add_zone(geometry=_square())
        items_a = view_a._ScanGeometry__scan_geometry_items.childItems()
        items_b = view_b._ScanGeometry__scan_geometry_items.childItems()
        assert len(items_a) == 1
        assert len(items_b) == 1

    def test_disabling_a_non_active_zone_removes_it_from_both_views(self, two_views):
        zones, view_a, view_b, _scene_a, _scene_b = two_views
        zones.add_zone(geometry=_square())  # zone 0, active by default
        zones.add_zone(geometry=_square(x=20.0))  # zone 1, not active
        assert len(view_a._ScanGeometry__scan_geometry_items.childItems()) == 2
        assert len(view_b._ScanGeometry__scan_geometry_items.childItems()) == 2

        zones.update_zone(1, enabled=False)

        items_a = view_a._ScanGeometry__scan_geometry_items.childItems()
        items_b = view_b._ScanGeometry__scan_geometry_items.childItems()
        assert len(items_a) == 1
        assert len(items_b) == 1


class TestViewerScanZonesConstructorContract:
    """``Viewer``'s ``scan_zones`` parameter: private by default, shared when
    an existing model is passed. Building a ``Viewer`` needs a
    ``QApplication``, provided by the module-scoped ``qapp`` fixture."""

    def test_two_viewers_with_no_model_get_distinct_models(self, qapp):
        viewer_a = Viewer()
        viewer_b = Viewer()
        assert viewer_a.scan_zones is not viewer_b.scan_zones

    def test_two_viewers_given_the_same_model_share_it(self, qapp):
        shared = ScanZones()
        viewer_a = Viewer(scan_zones=shared)
        viewer_b = Viewer(scan_zones=shared)
        assert viewer_a.scan_zones is shared
        assert viewer_b.scan_zones is shared


class TestDrawingPreviewColor:
    """The in-progress drawing outline takes the active zone's color, so it
    is obvious which zone a gesture will land in before releasing the mouse.
    Shift (subtract) keeps its own red signal, and an invalid outline its
    warning color, since neither is "drawing this zone"."""

    @staticmethod
    def _preview(viewer: Viewer) -> QColor:
        return viewer.zone_poly_item.pen().color()

    def test_add_uses_the_active_zones_color(self, qapp):
        zones = ScanZones()
        zones.add_zone(name="A", color="#ff5300")
        zones.add_zone(name="B", color="#00c8ff")
        viewer = Viewer(scan_zones=zones)

        zones.active_index = 0
        viewer._Viewer__update_selection_color(has_shift=False, is_valid=True)
        assert self._preview(viewer) == QColor("#ff5300")

        zones.active_index = 1
        viewer._Viewer__update_selection_color(has_shift=False, is_valid=True)
        assert self._preview(viewer) == QColor("#00c8ff")

    def test_fill_is_translucent_but_outline_is_not(self, qapp):
        zones = ScanZones()
        zones.add_zone(name="A", color="#ff5300")
        viewer = Viewer(scan_zones=zones)
        viewer._Viewer__update_selection_color(has_shift=False, is_valid=True)
        assert self._preview(viewer).alpha() == 255
        assert viewer.zone_poly_item.brush().color().alpha() == 64

    def test_subtract_stays_red_and_invalid_stays_a_warning(self, qapp):
        zones = ScanZones()
        zones.add_zone(name="A", color="#ff5300")
        viewer = Viewer(scan_zones=zones)

        viewer._Viewer__update_selection_color(has_shift=True, is_valid=True)
        assert self._preview(viewer) == QColor(QColorConstants.Red)

        viewer._Viewer__update_selection_color(has_shift=False, is_valid=False)
        assert self._preview(viewer) != QColor("#ff5300")

    def test_with_no_zones_previews_the_color_zone_1_will_get(self, qapp):
        zones = ScanZones()
        viewer = Viewer(scan_zones=zones)
        viewer._Viewer__update_selection_color(has_shift=False, is_valid=True)
        # Drawing here creates Zone 1, so the preview shows its future color.
        assert self._preview(viewer) == default_zone_color(0)
