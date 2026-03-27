"""Unit tests for laserstudio.utils.scanning."""

from __future__ import annotations

import random

import pytest
from shapely.geometry import MultiPolygon, Point, Polygon

from laserstudio.utils.scanning import (
    EmptyGeometryError,
    RandomPointGenerator,
    ScanPathGenerator,
)


def _unit_square() -> Polygon:
    return Polygon([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])


class TestRandomPointGenerator:
    def test_empty_multipolygon_is_empty_and_random_raises(self):
        gen = RandomPointGenerator()
        assert gen.is_empty()
        with pytest.raises(EmptyGeometryError):
            gen.random()

    def test_square_geometry_not_empty_triangles_cover_area(self):
        gen = RandomPointGenerator()
        gen.geometry = _unit_square()
        assert not gen.is_empty()
        tris = gen.debug_get_triangles()
        assert len(tris) >= 1
        total = sum(t[0] for t in tris)
        assert abs(total - 1.0) < 1e-6

    def test_random_points_inside_geometry(self):
        random.seed(12345)
        gen = RandomPointGenerator()
        square = _unit_square()
        gen.geometry = square
        for _ in range(30):
            x, y = gen.random()
            assert square.covers(Point(x, y)), (x, y)

    def test_multipolygon_merges_triangles(self):
        p1 = Polygon([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
        p2 = Polygon([(2.0, 0.0), (3.0, 0.0), (3.0, 1.0), (2.0, 1.0)])
        gen = RandomPointGenerator()
        gen.geometry = MultiPolygon([p1, p2])
        assert not gen.is_empty()
        total = sum(t[0] for t in gen.debug_get_triangles())
        assert abs(total - 2.0) < 1e-6


class TestScanPathGenerator:
    def test_empty_geometry_next_raises(self):
        gen = ScanPathGenerator()
        assert gen.is_empty()
        with pytest.raises(EmptyGeometryError):
            gen.next()

    def test_next_and_pop_return_points_inside_shape(self):
        random.seed(999)
        gen = ScanPathGenerator()
        gen.density = 8
        square = _unit_square()
        gen.geometry = square
        for _ in range(5):
            x, y = gen.next()
            assert square.covers(Point(x, y))
        random.seed(1001)
        gen2 = ScanPathGenerator()
        gen2.density = 8
        gen2.geometry = square
        x, y = gen2.pop()
        assert square.covers(Point(x, y))

    def test_density_invalid_raises(self):
        gen = ScanPathGenerator()
        gen.geometry = _unit_square()
        with pytest.raises(ValueError, match="Invalid density"):
            gen.density = 0

    def test_hist_list_respects_limit_and_requires_geometry(self):
        gen = ScanPathGenerator()
        gen.density = 5
        gen.geometry = _unit_square()
        # ScanPathGenerator.__history_size is 10
        with pytest.raises(ValueError, match="history size"):
            gen.hist_list(11)

        gen2 = ScanPathGenerator()
        with pytest.raises(EmptyGeometryError):
            gen2.hist_list(1)

    def test_hist_list_after_pop(self):
        random.seed(777)
        gen = ScanPathGenerator()
        gen.density = 4
        gen.geometry = _unit_square()
        gen.pop()
        gen.pop()
        h = gen.hist_list(2)
        assert len(h) == 2
        assert all(_unit_square().covers(Point(x, y)) for x, y in h)

    def test_next_list_length(self):
        random.seed(555)
        gen = ScanPathGenerator()
        gen.density = 10
        gen.geometry = _unit_square()
        pts = gen.next_list(7)
        assert len(pts) == 7
        assert all(_unit_square().covers(Point(x, y)) for x, y in pts)


class TestPolygonWithHole:
    """Checks that triangulation with a hole does not crash and still yields triangles."""

    def test_ring_with_hole_triangulates(self):
        outer = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]
        hole = [(1.0, 1.0), (1.0, 2.0), (2.0, 2.0), (2.0, 1.0)]
        poly = Polygon(outer, [hole])
        gen = RandomPointGenerator()
        gen.geometry = poly
        assert not gen.is_empty()
        for _ in range(15):
            x, y = gen.random()
            assert poly.covers(Point(x, y))
