"""Delaunay-triangulation based autofocus depth interpolation.

Drop-in replacement for :class:`pystages.Autofocus`, which always uses the
first 3 registered points (a single plane fit) regardless of how many points
are registered or where the query position actually is. This module instead
triangulates *all* registered (x, y) points (same ``triangle`` package usage
as :class:`laserstudio.utils.scanning.RandomPointGenerator`) and interpolates
the depth from the Delaunay triangle that contains the query point when there
is one, or extrapolates from the closest registered triangle otherwise.
"""

from __future__ import annotations

from shapely.geometry import Point, Polygon
from triangle import triangulate

Point3 = tuple[float, float, float]

# Tolerance for the point-in-triangle test, to accept points that fall
# exactly on a triangle edge (which happens often: a scan grid point is
# frequently registered right on the boundary between two triangles).
_EPS = 1e-9


class PointOutsideCoverageError(RuntimeError):
    """Raised by :meth:`DelaunayAutofocus.focus` when no triangle exists at
    all — fewer than 3 points are registered, or all registered points are
    collinear. ``pystages.Autofocus.focus`` raised a plain ``RuntimeError``
    in its "not enough points" case; this subclasses it so existing callers
    catching ``RuntimeError`` keep working. Being outside every triangle is
    *not* an error case: :meth:`focus` then extrapolates from the closest
    registered triangle instead."""


def _barycentric(a: Point3, b: Point3, c: Point3, x: float, y: float) -> tuple[float, float] | None:
    """
    Coordinates (u, v) of point (x, y) in the (ab, ac) basis rooted at a,
    i.e. (x, y) = a[:2] + u * (b[:2] - a[:2]) + v * (c[:2] - a[:2]).

    Valid (and used for extrapolation too) even when (x, y) is outside the
    triangle, i.e. u < 0, v < 0 or u + v > 1. Returns None only if a/b/c are
    collinear (degenerate triangle, no valid basis).
    """
    ab = (b[0] - a[0], b[1] - a[1])
    ac = (c[0] - a[0], c[1] - a[1])
    ap = (x - a[0], y - a[1])
    det = ab[0] * ac[1] - ab[1] * ac[0]
    if abs(det) < _EPS:
        return None
    u = (ap[0] * ac[1] - ap[1] * ac[0]) / det
    v = (ab[0] * ap[1] - ab[1] * ap[0]) / det
    return u, v


class DelaunayAutofocus:
    """
    Utility class to add autofocus support for scanning software. Given a
    set of focused coordinates, this class can calculate the correct Z-depth
    for other points, by Delaunay-triangulating the registered (x, y)
    positions and interpolating Z from the triangle that contains the query
    point — or, if the query point falls outside every registered triangle,
    extrapolating from the closest one instead.

    Public interface intentionally mirrors :class:`pystages.Autofocus`
    (``registered_points``, ``register``, ``clear``, ``focus``, ``__len__``)
    so it is a drop-in replacement for existing callers.
    """

    def __init__(self) -> None:
        self.registered_points: list[Point3] = []

    def register(self, x: float, y: float, z: float) -> None:
        """
        Register a new focused point.

        :param x: Abscissa of the point.
        :param y: Ordinate of the point.
        :param z: Depth of the point.
        """
        self.registered_points.append((x, y, z))

    def remove(self, index: int) -> None:
        """Remove a single registered point by its index."""
        del self.registered_points[index]

    def clear(self) -> None:
        """Remove all registration points."""
        self.registered_points.clear()

    def __len__(self) -> int:
        """:return: Number of registered points."""
        return len(self.registered_points)

    def _triangulation(self) -> list[tuple[int, int, int]]:
        # Recomputed on every call rather than cached: registered_points is a
        # plain list that some callers (e.g. the classic focus toolbar)
        # mutate directly (list.pop) without going through register()/
        # remove(), so a cache could silently go stale and return triangles
        # indexing points that have since moved. Triangulating a few hundred
        # points is inexpensive, and autofocus queries are not a hot path.
        return self._compute_triangulation()

    def _compute_triangulation(self) -> list[tuple[int, int, int]]:
        points = self.registered_points
        if len(points) < 3:
            return []
        vertices = [(x, y) for x, y, _ in points]
        try:
            result = triangulate({"vertices": vertices})
        except ValueError:
            # Fewer than 3 vertices, or another degenerate input rejected
            # outright by the triangle library.
            return []
        triangles = result.get("triangles")
        if triangles is None:
            # E.g. all registered points are collinear: no triangle exists.
            return []
        return [(int(t[0]), int(t[1]), int(t[2])) for t in triangles]

    def locate(self, x: float, y: float) -> tuple[int, int, int] | None:
        """
        Find the Delaunay triangle (as a triple of indices into
        ``registered_points``) that contains (x, y).

        :return: The triangle's point indices, or None if (x, y) is outside
            every registered triangle (or no triangle exists at all).
        """
        points = self.registered_points
        for triangle_indices in self._triangulation():
            ia, ib, ic = triangle_indices
            bary = _barycentric(points[ia], points[ib], points[ic], x, y)
            if bary is None:
                continue
            u, v = bary
            if u >= -_EPS and v >= -_EPS and (u + v) <= 1 + _EPS:
                return triangle_indices
        return None

    def nearest(self, x: float, y: float) -> tuple[int, int, int] | None:
        """
        Find the Delaunay triangle closest to (x, y) (0 distance if (x, y) is
        inside one), to use as an extrapolation basis when :meth:`locate`
        finds none.

        :return: The closest triangle's point indices, or None if no
            triangle exists at all (fewer than 3 points registered, or all
            registered points are collinear).
        """
        points = self.registered_points
        query = Point(x, y)
        best: tuple[int, int, int] | None = None
        best_distance: float | None = None
        for triangle_indices in self._triangulation():
            ia, ib, ic = triangle_indices
            polygon = Polygon(
                [points[ia][:2], points[ib][:2], points[ic][:2]]
            )
            distance = polygon.distance(query)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best = triangle_indices
        return best

    def is_covered(self, x: float, y: float) -> bool:
        """:return: True if (x, y) is exactly inside a registered triangle
        (a :meth:`focus` call there interpolates rather than extrapolates)."""
        return self.locate(x, y) is not None

    def can_focus_at(self, x: float, y: float) -> bool:
        """:return: True if :meth:`focus` can produce an estimate at (x, y)
        at all — i.e. at least one (non-degenerate) triangle is registered,
        whether or not (x, y) actually falls inside it."""
        return self.nearest(x, y) is not None

    def focus(self, x: float, y: float) -> float:
        """
        Guess the correct focus depth given abscissa and ordinate of a new
        point: interpolate Z across the Delaunay triangle that contains
        (x, y) if there is one, otherwise extrapolate from the closest
        registered triangle.

        :param x: Abscissa of the point.
        :param y: Ordinate of the point.
        :return: Interpolated (or extrapolated) depth.
        :raises PointOutsideCoverageError: If fewer than 3 points are
            registered, or if all registered points are collinear (no
            triangle exists at all to extrapolate from).
        """
        triangle_indices = self.locate(x, y)
        if triangle_indices is None:
            triangle_indices = self.nearest(x, y)
        if triangle_indices is None:
            raise PointOutsideCoverageError(
                f"No Delaunay triangle could be formed from the "
                f"{len(self.registered_points)} registered autofocus point(s)"
            )
        ia, ib, ic = triangle_indices
        a = self.registered_points[ia]
        b = self.registered_points[ib]
        c = self.registered_points[ic]
        bary = _barycentric(a, b, c, x, y)
        assert bary is not None
        u, v = bary
        return a[2] + u * (b[2] - a[2]) + v * (c[2] - a[2])
