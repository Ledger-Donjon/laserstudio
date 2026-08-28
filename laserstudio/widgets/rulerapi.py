"""
Ruler operations exposed through the REST API and the MCP server.

These functions take the :class:`~laserstudio.widgets.viewer.Viewer` they act on
instead of a main window, so the ruler API belongs to the viewer and not to any
particular interface. A window hosting a viewer only has to forward its
``handle_*`` API methods here.
"""
from __future__ import annotations

from PyQt6.QtGui import QColor

from ..restserver.errors import InvalidParameterError
from ..utils.yaml_types import Config
from .viewer import Viewer


def rulers(viewer: Viewer) -> list[Config]:
    """List the rulers of *viewer*.

    :param viewer: The viewer holding the rulers.
    :return: One dictionary per ruler, as returned by :meth:`Ruler.to_dict`.
    """
    return [ruler.to_dict() for ruler in viewer.rulers]


def add_rulers(
    viewer: Viewer,
    segments: list[list[float]] | None,
    color: list[float] | None,
    label: str | None,
    graduation: float | None = None,
    graduation_count: float | None = None,
    visible: bool | None = True,
) -> Config:
    """Add ruler(s) to *viewer*.

    :param viewer: The viewer to add the ruler(s) to.
    :param segments: The requested segment(s), each given as the four
        coordinates ``[x1, y1, x2, y2]`` of its endpoints.
    :param color: The requested color of the ruler(s). Defined as a list of 3 floats
        from 0.0 to 1.0 (RGB) or 4 floats from 0.0 to 1.0 (RGBA).
    :param label: The requested label of the ruler(s).
    :param graduation: The requested graduation interval, in micrometers.
        If None or 0, the ruler(s) are drawn without graduations.
    :param graduation_count: The requested number of graduations over the whole
        ruler, as an alternative to *graduation*: each ruler keeps that count and
        derives its interval from its own length. Giving both is an error.
    :param visible: If False, ruler(s) are created but not displayed.
    :return: A dictionary containing the information about the created ruler(s)
    """
    if visible is None:
        visible = True
    if graduation and graduation_count:
        raise InvalidParameterError(
            "Only one of 'graduation' and 'graduation_count' can be given.",
            details={"graduation": graduation, "graduation_count": graduation_count},
        )
    if graduation_count is not None and graduation_count <= 0:
        raise InvalidParameterError(
            "Graduation count argument is invalid. It should be strictly positive.",
            details={"graduation_count": graduation_count},
        )
    if not segments:
        raise InvalidParameterError(
            "Segments argument is missing. At least one segment "
            "[x1, y1, x2, y2] is required.",
            details={"segments": segments},
        )
    for segment in segments:
        if len(segment) != 4:
            raise InvalidParameterError(
                "Segment argument is invalid. It should be a list of 4 floats "
                "[x1, y1, x2, y2].",
                details={"segment": segment},
            )

    qcolor = None
    if color is not None:
        if len(color) == 3:
            color.append(1.0)
        if len(color) != 4:
            raise InvalidParameterError(
                "Color argument is invalid. It should be a list of 3 or 4 floats.",
                details={"color": color},
            )
        qcolor = QColor(
            int(color[0] * 255),
            int(color[1] * 255),
            int(color[2] * 255),
            int(color[3] * 255),
        )

    created = [
        viewer.add_ruler(
            (segment[0], segment[1]),
            (segment[2], segment[3]),
            color=qcolor,
            label=label,
            graduation=graduation,
            graduation_count=graduation_count,
            visible=visible,
        )
        for segment in segments
    ]

    if len(created) == 1:
        return created[0].to_dict()
    return {"rulers": [ruler.to_dict() for ruler in created]}


def delete_rulers(viewer: Viewer, ids: list[int] | None = None) -> Config:
    """Delete ruler(s) from *viewer*.

    :param viewer: The viewer to remove the ruler(s) from.
    :param ids: The identifiers of the rulers to delete. If None or empty,
        all rulers are removed.
    :return: A dictionary containing the list of deleted ruler identifiers
        under the ``deleted`` key.
    """
    if not ids:
        deleted = [ruler.id for ruler in viewer.rulers]
        viewer.clear_rulers()
        return {"deleted": deleted}

    id_set = set(ids)
    deleted = []
    for ruler in viewer.rulers:
        if ruler.id in id_set:
            viewer.remove_ruler(ruler)
            deleted.append(ruler.id)
    return {"deleted": deleted}
