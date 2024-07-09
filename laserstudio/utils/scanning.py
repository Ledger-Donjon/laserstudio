# Utility methods for circuit scanning.
# Uses shapely and triangle libraries.
# shapely is usually available through debian repositories.
# triangle can be installed with pip3.

from shapely.geometry import MultiPolygon, Polygon, GeometryCollection
import random
from typing import Union, Optional, cast
from triangle import triangulate

Point = tuple[float, float]
Path = list[Point]
# Triangle is the area and three points
Triangle = tuple[float, Point, Point, Point]


class EmptyGeometryError(Exception):
    pass


# TODO: do lazy updating to have better performances: only update when random
# point generation is called
class RandomPointGenerator:
    """
    Given a geometry, this class helps generating random points in that
    geometry. Distribution is homogeneous.
    """

    def __init__(self):
        self.__geometry = MultiPolygon()
        # list of triangles and weight. Each element of this list is a tuple.
        # First element of tuple is triangle area.
        # Next three elements are the points of the triangle.
        self.__triangles = []

    def __update(self):
        """
        Called when the geometry is changed. Perform some calculations to be
        ready to generate random points.
        """
        self.__triangles = self.__triangulate(self.__geometry)
        self.__total_area = 0.0
        for area, _, _, _ in self.__triangles:
            self.__total_area += area

    def __triangulate(self, geometry: Union[MultiPolygon, Polygon]) -> list[Triangle]:
        """
        Triangulate a geometry using Constrained Delaunay Triangulation.
        :param geometry: A shapely geometry.
        :return: A list of tuple. For each tuple, the first element is the
        triangle area and the other elements are the 3 points of the triangle.
        """
        result = []

        # If the geometry is a multipolygon, call this method recursively.
        if isinstance(geometry, MultiPolygon) or isinstance(
            geometry, GeometryCollection
        ):
            for poly in geometry.geoms:
                result += self.__triangulate(poly)
        else:
            ext_count = len(geometry.exterior.coords) - 1
            if ext_count == -1:
                # Empty shape
                return []

            # list of vertices
            # With shapely, last vertex is also the first one. Skip it
            # otherwise Triangle may crash.
            vertices = list(geometry.exterior.coords[:-1])

            # list of edges which are forced in the triangulation. Add the edges
            # of the exterior and interior rings.
            segments = []
            holes = []

            for i in range(len(vertices)):
                segments.append((i, (i + 1) % ext_count))

            for interior in geometry.interiors:
                holes.append(interior.representative_point().coords[0])
                start = len(vertices)
                vertices += list(interior.coords[:-1])
                int_count = len(interior.coords) - 1  # Number of vertices
                for i in range(int_count):
                    segments.append((start + i, start + ((i + 1) % int_count)))

            triangulation = triangulate(
                {"vertices": vertices, "segments": segments}, "pc"
            )
            for triangle in triangulation["triangles"]:
                points = []
                for i in triangle:
                    points.append(triangulation["vertices"][i])
                polygon = Polygon(points)
                if geometry.contains(polygon.representative_point()):
                    area = polygon.area
                    coords = tuple(polygon.exterior.coords[:-1])
                    assert len(coords) == 3
                    c = cast(tuple[Point, Point, Point], coords)
                    t = area, *c
                    result.append(t)
        return result

    def random(self) -> Point:
        """
        Generate a random point in the geometry.
        :return: (x, y) tuple.
        :raises: EmptyGeometryError if the shape is empty.
        """
        if self.is_empty():
            raise EmptyGeometryError()
        # Pick a random triangle
        # Polygon area must be take into account.
        r = random.random() * self.__total_area
        chosen_triangle = None
        area_acc = 0
        for triangle in self.__triangles:
            area_acc += triangle[0]
            if r <= area_acc:
                chosen_triangle = triangle
                break
        assert chosen_triangle is not None  # This should not happen
        # Pick a random point in the triangle
        a, b, c = chosen_triangle[1:]
        rand_a = random.random()
        rand_b = random.random()
        # Random is picked in a rectangle. Fold coordinates to pick in a
        # triangle.
        if rand_a + rand_b > 1:
            rand_a = 1 - rand_a
            rand_b = 1 - rand_b
        x = a[0] + (b[0] - a[0]) * rand_a + (c[0] - a[0]) * rand_b
        y = a[1] + (b[1] - a[1]) * rand_a + (c[1] - a[1]) * rand_b
        return x, y

    def is_empty(self) -> bool:
        """:return: True if geometry is empty."""
        return len(self.__triangles) == 0

    @property
    def geometry(self):
        """:return: Current geometry."""
        return self.__geometry

    @geometry.setter
    def geometry(self, value):
        """
        Change the geometry used for random points calculation.
        :param value: The new geometry. Any shapely geometry.
        """
        self.__geometry = value
        self.__update()

    def debug_get_triangles(self) -> list[Triangle]:
        return self.__triangles


class ScanPathGenerator(RandomPointGenerator):
    """
    This class helps generating a random scanning path. If a path of N points is
    requested, N points are randomly chosen in the given geometry using the
    RandomPointGenerator. These N points are then ordered to reduce the distance
    between consecutive points.
    """

    def __init__(self):
        super().__init__()
        # Number of points for each path.
        # The highest it is, the smaller is the mean distance between
        # consecutive points.
        self.__density = 100
        # Number of old scanning points to be memorized in the history.
        self.__history_size = 10
        # History of scanned points
        self.__history: Path = []
        # Generated paths
        # We may need to know the next paths if the user wants to display the
        # next points to be scanned when end of current path is reached.
        self.__paths: list[Path] = []
        # Index of the next point in the first path.
        self.__next_index: int = 0
        # Total number of points in all paths.
        self.__total: int = 0

    @RandomPointGenerator.geometry.setter
    def geometry(self, value):
        """
        Change the geometry used for random path generation. Changing the
        geometry will generate a new scan path.

        :param value: The new geometry. Any shapely geometry.
        """
        assert RandomPointGenerator.geometry.fset is not None
        RandomPointGenerator.geometry.fset(self, value)
        self.__reset()

    def __reset(self):
        """
        Clear current scanning path and generate a new one. Start of the new
        path will be near the next point of the current path. This method is
        called when the geometry is updated or when the density is changed.
        """
        if (self.geometry is None) or (self.is_empty()):
            self.__paths.clear()
            self.__total = 0
            self.__next_index = 0
        else:
            # Get the start point
            start = self.next()
            # Clear all paths
            self.__paths.clear()
            self.__next_index = 0
            path = self.__generate_path(self.__density, start)
            self.__paths.append(path)
            self.__total = len(path)

    def __generate_path(self, length: int, start: Optional[Point] = None) -> Path:
        """
        Generate a new scan path.

        :param length: Number of points.
        :param start: Hint point. The algorithm will pick the nearest point to
        start as the first point in the path.
        """
        # Pick the random points.
        points: list[Point] = []
        for _ in range(length):
            points.append(self.random())
        # Get the first points
        result: Path = []
        if start is None:
            result.append(points.pop())
        else:
            result.append(points.pop(self.__nearest(start, points)))
        # Build the path.
        while len(points):
            result.append(points.pop(self.__nearest(result[-1], points)))
        return result

    @staticmethod
    def __nearest(point: Point, points: list[Point]) -> int:
        """
        Find the nearest point in a list.

        :param point: Interest point.
        :param points: list of points.
        :return: Index of the nearest point in the list. 0 if the list is empty
        """
        nearest_dist_sqr = float("inf")
        nearest_index = 0
        for i, p in enumerate(points):
            dist_sqr = ((point[0] - p[0]) ** 2) + ((point[1] - p[1]) ** 2)
            if dist_sqr < nearest_dist_sqr:
                nearest_dist_sqr = dist_sqr
                nearest_index = i
        return nearest_index

    def __require_n(self, n: int):
        """
        Build new paths until n next points are available.

        :param n: Number of points required.
        """
        while (self.__total - self.__next_index) < n:
            # Pick the starting point
            if len(self.__paths) > 0:
                start = self.__paths[-1][-1]
            else:
                # This is the first generated point, no chaining to be done.
                start = None
            # Generate the new path
            new_path = self.__generate_path(self.__density, start)
            self.__paths.append(new_path)
            self.__total += len(new_path)

    def pop(self) -> Point:
        """
        Pop and return the next scan point.

        :return: Next point to be scanned.
        """
        self.__require_n(1)
        p = self.__paths[0][self.__next_index]
        self.__next_index += 1
        if self.__next_index >= len(self.__paths[0]):
            self.__next_index = 0
            self.__total -= len(self.__paths[0])
            self.__paths = self.__paths[1:]
        self.__history.append(p)
        if len(self.__history) > self.__history_size:
            self.__history = self.__history[-self.__history_size :]
        return p

    def next(self) -> Point:
        """
        :return: Next point to be scanned.
        """
        return self.next_list(1)[0]

    def next_list(self, n: int) -> Path:
        """
        :return: list of next points to be scanned.
        :param n: Number of points to be returned.
        """
        if self.is_empty():
            raise EmptyGeometryError()
        result = []
        self.__require_n(n)
        i = 0
        j = self.__next_index
        for _ in range(n):
            result.append(self.__paths[i][j])
            j += 1
            if j >= len(self.__paths[i]):
                i += 1
                j = 0
        return result

    def hist_list(self, n: int) -> Path:
        """
        :return: Last n scanned points. The size of the result may be smaller
        than n if there are not enough points in the history.
        :n: Number of points to be returned. Must be lower of equal to history
        size.
        """
        if self.is_empty():
            raise EmptyGeometryError()
        if n > self.__history_size:
            raise ValueError("n bigger than history size limit.")
        return self.__history[-n:]

    @property
    def density(self) -> int:
        """
        Number of points generated randomly in the scan shape. The bigger it
        is, the smaller average distance between consecutive points is.
        Changing this parameter will generate a new set of points.
        """
        return self.__density

    @density.setter
    def density(self, value: int):
        if value < 1:
            raise ValueError("Invalid density")
        self.__density = value
        self.__reset()
