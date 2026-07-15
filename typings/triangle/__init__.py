# Partial stubs for the `triangle` package (PyPI: triangle).
# Covers only the API used by laserstudio.utils.scanning.

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict

from numpy.typing import NDArray


class TriangulateOutput(TypedDict):
    """Return shape of ``triangulate(..., \"pc\")`` on a PSLG (as in scanning)."""

    vertices: NDArray[Any]
    vertex_markers: NDArray[Any]
    triangles: NDArray[Any]
    segments: NDArray[Any]
    segment_markers: NDArray[Any]


def triangulate(
    tri: Mapping[str, Any],
    opts: str = "",
) -> TriangulateOutput:
    """Constrained Delaunay triangulation; ``opts`` e.g. ``\"pc\"`` (PSLG)."""
