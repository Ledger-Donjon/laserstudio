"""Tests for laserstudio.instruments.autofocus_triangulation.DelaunayAutofocus."""

import pytest

from laserstudio.instruments.autofocus_triangulation import (
    DelaunayAutofocus,
    PointOutsideCoverageError,
    _barycentric,
)


def _plane(x: float, y: float) -> float:
    """An arbitrary tilted plane, used as ground truth for interpolation."""
    return 2.0 * x + 3.0 * y + 10.0


def _square_grid_autofocus() -> DelaunayAutofocus:
    """A 2x2 unit-square grid of points registered on the plane above."""
    af = DelaunayAutofocus()
    for x, y in [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0), (10.0, 10.0)]:
        af.register(x, y, _plane(x, y))
    return af


def test_empty_raises():
    af = DelaunayAutofocus()
    assert len(af) == 0
    assert not af.can_focus_at(0.0, 0.0)
    with pytest.raises(PointOutsideCoverageError):
        af.focus(0.0, 0.0)


def test_fewer_than_three_points_raises():
    af = DelaunayAutofocus()
    af.register(0.0, 0.0, 1.0)
    af.register(1.0, 1.0, 2.0)
    assert len(af) == 2
    assert not af.can_focus_at(0.5, 0.5)
    with pytest.raises(PointOutsideCoverageError):
        af.focus(0.5, 0.5)


def test_collinear_points_raise():
    af = DelaunayAutofocus()
    for x in (0.0, 1.0, 2.0):
        af.register(x, x, _plane(x, x))
    assert len(af) == 3
    with pytest.raises(PointOutsideCoverageError):
        af.focus(1.0, 1.0)


def test_flat_plane_interpolates_inside_triangle():
    af = DelaunayAutofocus()
    for x, y in [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0)]:
        af.register(x, y, 5.0)
    assert af.can_focus_at(2.0, 2.0)
    assert af.focus(2.0, 2.0) == pytest.approx(5.0)


def test_tilted_plane_interpolates_inside_grid():
    af = _square_grid_autofocus()
    for x, y in [(1.0, 1.0), (5.0, 5.0), (9.0, 1.0), (1.0, 9.0), (5.0, 2.0)]:
        assert af.can_focus_at(x, y)
        assert af.focus(x, y) == pytest.approx(_plane(x, y))


def test_point_outside_convex_hull_extrapolates_instead_of_raising():
    af = _square_grid_autofocus()
    # Still "usable" (a triangle exists to extrapolate from)...
    assert af.can_focus_at(50.0, 50.0)
    # ...but not exactly covered.
    assert not af.is_covered(50.0, 50.0)
    # All registered points lie on the same plane, so extrapolating from any
    # triangle still reproduces that plane exactly, however far outside the
    # registered area the query point is.
    assert af.focus(50.0, 50.0) == pytest.approx(_plane(50.0, 50.0))


def test_focus_outside_hull_matches_nearest_triangle_extrapolation():
    # A non-planar height field: which triangle nearest() picks now actually
    # changes the extrapolated value, unlike the single-plane fixture above.
    af = DelaunayAutofocus()
    af.register(0.0, 0.0, 0.0)
    af.register(10.0, 0.0, 0.0)
    af.register(0.0, 10.0, 0.0)
    af.register(10.0, 10.0, 100.0)

    x, y = 50.0, -50.0
    triangle_indices = af.nearest(x, y)
    assert triangle_indices is not None
    assert not af.is_covered(x, y)
    ia, ib, ic = triangle_indices
    a, b, c = (af.registered_points[i] for i in (ia, ib, ic))
    bary = _barycentric(a, b, c, x, y)
    assert bary is not None
    u, v = bary
    expected = a[2] + u * (b[2] - a[2]) + v * (c[2] - a[2])
    assert af.focus(x, y) == pytest.approx(expected)


def test_point_on_shared_edge_is_covered_and_consistent():
    # The diagonal of the 2x2 grid is a shared edge between the two
    # triangles of the triangulation: interpolation must agree with the
    # ground truth regardless of which triangle claims the point.
    af = _square_grid_autofocus()
    assert af.can_focus_at(5.0, 5.0)
    assert af.focus(5.0, 5.0) == pytest.approx(_plane(5.0, 5.0))


def test_remove_updates_coverage():
    af = _square_grid_autofocus()
    assert af.can_focus_at(5.0, 5.0)
    # Remove points until fewer than 3 remain: coverage must disappear.
    af.remove(0)
    af.remove(0)
    assert len(af) == 2
    assert not af.can_focus_at(5.0, 5.0)


def test_direct_list_mutation_does_not_corrupt_state():
    """The classic focus toolbar mutates `registered_points` directly
    (list.pop) instead of calling remove(); the triangulation must not be
    cached in a way that goes stale when that happens."""
    af = _square_grid_autofocus()
    af.registered_points.pop(0)
    assert len(af) == 3
    x, y, _ = af.registered_points[0]
    remaining = af.registered_points
    cx = sum(p[0] for p in remaining) / 3
    cy = sum(p[1] for p in remaining) / 3
    assert af.can_focus_at(cx, cy)
    assert af.focus(cx, cy) == pytest.approx(_plane(cx, cy))


def test_clear_resets_coverage():
    af = _square_grid_autofocus()
    af.clear()
    assert len(af) == 0
    assert not af.can_focus_at(5.0, 5.0)
