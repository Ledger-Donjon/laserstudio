"""Affine alignment of a background reference image from 3 point pairs."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PyQt6.QtGui import QTransform


@dataclass(frozen=True)
class BackgroundPin:
    """One correspondence between an image pixel and a stage/scene position."""

    image_px: tuple[float, float]
    stage_xy: tuple[float, float]

    def as_pair(self) -> tuple[tuple[float, float], tuple[float, float]]:
        return self.stage_xy, self.image_px


def compute_affine_transform(
    pins: list[BackgroundPin] | list[tuple[tuple[float, float], tuple[float, float]]],
) -> QTransform | None:
    """
    Compute the 2D affine map from image pixels to scene/stage coordinates.

    Each pin maps ``image_px`` → ``stage_xy`` (same convention as ``Viewer.pin``).
    """
    if len(pins) != 3:
        return None

    pairs: list[tuple[tuple[float, float], tuple[float, float]]]
    if pins and isinstance(pins[0], BackgroundPin):
        pairs = [p.as_pair() for p in pins]  # type: ignore[union-attr]
    else:
        pairs = pins  # type: ignore[assignment]

    points_a = [p[0] + (1.0,) for p in pairs]
    points_b = [p[1] + (1.0,) for p in pairs]
    mat_a = np.matrix(points_a).transpose()
    mat_b = np.matrix(points_b).transpose()
    try:
        mat = mat_a * np.linalg.inv(mat_b)
    except np.linalg.LinAlgError:
        return None
    return QTransform(*mat.flatten().tolist()[0]).transposed()
