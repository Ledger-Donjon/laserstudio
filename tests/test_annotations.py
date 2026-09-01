"""Unit tests for the shared annotations model and multi-viewer sync."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication

from laserstudio.instruments.annotations import AnnotationsInstrument
from laserstudio.widgets.viewer import Viewer


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def annotations() -> AnnotationsInstrument:
    return AnnotationsInstrument({})


def test_add_ruler_stores_model(annotations: AnnotationsInstrument):
    ruler = annotations.add_ruler((0.0, 0.0), (100.0, 0.0), label="pitch")

    assert ruler.id == 1
    assert ruler.length == pytest.approx(100.0)
    assert ruler.label == "pitch"
    assert 1 in annotations.rulers


def test_settings_round_trip(annotations: AnnotationsInstrument):
    annotations.add_ruler((0.0, 0.0), (3.0, 4.0), label="a")
    annotations.default_marker_size = 15.0

    payload = annotations.settings
    restored = AnnotationsInstrument({})
    restored.settings = payload

    assert restored.default_marker_size == pytest.approx(15.0)
    assert len(restored.rulers) == 1
    assert restored.rulers[1].length == pytest.approx(5.0)


def test_rulers_sync_between_two_viewers(app: QApplication):
    annotations = AnnotationsInstrument({})
    classic = Viewer(annotations=annotations)
    new_ui = Viewer(annotations=annotations)

    classic.add_ruler((0.0, 0.0), (50.0, 0.0), label="shared")

    assert len(classic.rulers) == 1
    assert len(new_ui.rulers) == 1
    assert classic.rulers[0].id == new_ui.rulers[0].id
    assert classic.rulers[0].label == "shared"

    classic.rulers[0].set_endpoint(1, QPointF(200.0, 0.0))
    assert new_ui.rulers[0].length == pytest.approx(200.0)

    new_ui.clear_rulers()
    assert classic.rulers == []
    assert new_ui.rulers == []


def test_load_markers_from_json_file(app: QApplication, tmp_path: Path):
    viewer = Viewer(annotations=AnnotationsInstrument({}))
    path = tmp_path / "markers.json"
    path.write_text(
        json.dumps(
            [
                {"id": 3, "pos": [10.0, 20.0], "color": [1.0, 0.0, 0.0], "label": "A"},
                {"pos": [30.0, 40.0], "color": [0.0, 1.0, 0.0, 0.5]},
            ]
        ),
        encoding="utf-8",
    )

    viewer.load_markers(str(path), interactive=False)

    assert len(viewer.markers) == 2
    assert viewer.markers[0].id == 3
    assert viewer.markers[0].pos().x() == pytest.approx(10.0)
    assert viewer.markers[0].label == "A"
