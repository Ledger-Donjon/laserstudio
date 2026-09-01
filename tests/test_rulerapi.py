"""Unit tests for laserstudio.widgets.rulerapi.

The ruler API is exercised against a bare Viewer, with no main window, to check
that the REST/MCP ruler endpoints only need a viewer to operate.
"""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from laserstudio.restserver.errors import InvalidParameterError
from laserstudio.widgets import rulerapi
from laserstudio.widgets.viewer import Viewer


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def viewer(app: QApplication) -> Viewer:
    return Viewer()


def test_add_ruler_returns_its_geometry(viewer: Viewer):
    result = rulerapi.add_rulers(
        viewer,
        [[0.0, 0.0, 300.0, 400.0]],
        [1.0, 0.0, 0.0],
        "pitch",
        10.0,
        visible=True,
    )

    assert result["length"] == pytest.approx(500.0)
    assert result["p1"] == [0.0, 0.0]
    assert result["p2"] == [300.0, 400.0]
    assert result["color"] == [1.0, 0.0, 0.0, 1.0]
    assert result["label"] == "pitch"
    assert result["graduation"] == 10.0
    assert len(viewer.rulers) == 1


def test_add_several_rulers_lists_them(viewer: Viewer):
    result = rulerapi.add_rulers(
        viewer, [[0.0, 0.0, 3.0, 4.0], [0.0, 0.0, 6.0, 8.0]], None, None
    )

    lengths = [ruler["length"] for ruler in result["rulers"]]
    assert lengths == pytest.approx([5.0, 10.0])


def test_rulers_lists_the_viewer_rulers(viewer: Viewer):
    assert rulerapi.rulers(viewer) == []
    rulerapi.add_rulers(viewer, [[0.0, 0.0, 3.0, 4.0]], None, None)
    assert [ruler["length"] for ruler in rulerapi.rulers(viewer)] == [5.0]


def test_add_ruler_with_graduation_count_keeps_the_count(viewer: Viewer):
    result = rulerapi.add_rulers(
        viewer, [[0.0, 0.0, 150.0, 0.0]], None, None, graduation_count=10
    )

    # The count is what the ruler stores; the interval is derived from it.
    assert result["graduation_count"] == 10
    assert "graduation" not in result
    assert viewer.rulers[0].effective_graduation == pytest.approx(15.0)


def test_graduation_count_derives_a_per_ruler_interval(viewer: Viewer):
    rulerapi.add_rulers(
        viewer,
        [[0.0, 0.0, 150.0, 0.0], [0.0, 0.0, 0.0, 500.0]],
        None,
        None,
        graduation_count=10,
    )

    intervals = [ruler.effective_graduation for ruler in viewer.rulers]
    assert intervals == pytest.approx([15.0, 50.0])


def test_add_ruler_with_both_graduation_forms_is_rejected(viewer: Viewer):
    with pytest.raises(InvalidParameterError):
        rulerapi.add_rulers(
            viewer, [[0.0, 0.0, 150.0, 0.0]], None, None, 10.0, graduation_count=10
        )


def test_add_ruler_with_zero_graduation_count_is_rejected(viewer: Viewer):
    with pytest.raises(InvalidParameterError):
        rulerapi.add_rulers(
            viewer, [[0.0, 0.0, 150.0, 0.0]], None, None, graduation_count=0
        )


def test_add_ruler_without_segment_is_rejected(viewer: Viewer):
    with pytest.raises(InvalidParameterError):
        rulerapi.add_rulers(viewer, None, None, None)


def test_add_ruler_with_incomplete_segment_is_rejected(viewer: Viewer):
    with pytest.raises(InvalidParameterError):
        rulerapi.add_rulers(viewer, [[0.0, 0.0, 1.0]], None, None)


def test_add_ruler_with_invalid_color_is_rejected(viewer: Viewer):
    with pytest.raises(InvalidParameterError):
        rulerapi.add_rulers(viewer, [[0.0, 0.0, 1.0, 1.0]], [0.5, 0.5], None)


def test_delete_rulers_by_id_keeps_the_others(viewer: Viewer):
    first = rulerapi.add_rulers(viewer, [[0.0, 0.0, 3.0, 4.0]], None, None)["id"]
    second = rulerapi.add_rulers(viewer, [[0.0, 0.0, 6.0, 8.0]], None, None)["id"]

    assert rulerapi.delete_rulers(viewer, [first]) == {"deleted": [first]}
    assert [ruler.id for ruler in viewer.rulers] == [second]


def test_delete_rulers_without_id_removes_all(viewer: Viewer):
    rulerapi.add_rulers(
        viewer, [[0.0, 0.0, 3.0, 4.0], [0.0, 0.0, 6.0, 8.0]], None, None
    )

    assert len(rulerapi.delete_rulers(viewer)["deleted"]) == 2
    assert viewer.rulers == []
