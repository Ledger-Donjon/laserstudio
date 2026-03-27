"""
Runtime checks that the local `typings/triangle` stub matches how
laserstudio.utils.scanning uses ``triangle.triangulate``.
"""

from __future__ import annotations

from shapely.geometry import Polygon

from triangle import triangulate


def _triangulate_like_scanning(geometry: Polygon) -> list[tuple[float, float, float]]:
    """
    Same triangulate call and vertex/triangle indexing pattern as
    RandomPointGenerator.__triangulate (exterior only, no holes).
    Returns triangle areas for sanity checks.
    """
    ext_count = len(geometry.exterior.coords) - 1
    vertices = list(geometry.exterior.coords[:-1])
    segments = [(i, (i + 1) % ext_count) for i in range(len(vertices))]

    triangulation = triangulate({"vertices": vertices, "segments": segments}, "pc")

    assert "triangles" in triangulation
    assert "vertices" in triangulation

    areas: list[float] = []
    for triangle in triangulation["triangles"]:
        points = []
        for i in triangle:
            row = triangulation["vertices"][i]
            points.append((float(row[0]), float(row[1])))
        poly = Polygon(points)
        if geometry.contains(poly.representative_point()):
            areas.append(poly.area)

    return areas


def test_triangulate_square_pc_returns_vertices_and_triangles():
    """PSLG square: two triangles, same indexing pattern as scanning."""
    square = Polygon([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
    areas = _triangulate_like_scanning(square)
    assert len(areas) == 2
    assert abs(sum(areas) - 1.0) < 1e-9


def test_triangulate_triangle_pc_single_triangle():
    ext = [(0.0, 0.0), (2.0, 0.0), (1.0, 3.0)]
    poly = Polygon(ext + [ext[0]])
    areas = _triangulate_like_scanning(poly)
    assert len(areas) == 1
    assert abs(areas[0] - poly.area) < 1e-9
