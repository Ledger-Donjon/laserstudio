"""Unit tests for laserstudio.widgets.workspace.analyzeworkspace.AnalyzeWorkspace.

The panel is built headlessly (QT_QPA_PLATFORM=offscreen) on top of a real
``Viewer``, and driven like a user would: clicking the Ruler button, then
checking the viewer mode actually followed.

``Workspace`` derives from ``QObject``: a subclass that forgets to call
``super().__init__()`` still builds a working-looking panel, but every
connection to one of its bound methods is silently dropped. That is exactly
what broke the Ruler button, hence the tests below go through the signals
rather than calling the handlers directly.
"""

from __future__ import annotations

import os

# Must be set before QApplication is constructed.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QWidget

from laserstudio.instruments.annotations import AnnotationsInstrument
from laserstudio.widgets.viewer import Viewer
from laserstudio.widgets.workspace.analyzeworkspace import AnalyzeWorkspace


@pytest.fixture(scope="module")
def qapp():
    """A single QApplication for the whole module."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _StubWindow:
    """The only thing the panel asks its window for is the shared viewer."""

    def __init__(self, viewer: Viewer) -> None:
        self.viewer = viewer
        self.panel: QWidget | None = None


@pytest.fixture
def workspace(qapp: QApplication) -> AnalyzeWorkspace:
    viewer = Viewer(annotations=AnnotationsInstrument({}))
    window = _StubWindow(viewer)
    ws = AnalyzeWorkspace(window)
    # The real window parents the panel into its sidebar; here nothing else
    # owns it, so hold it for the duration of the test.
    window.panel = ws.build_panel()
    return ws


def test_ruler_button_puts_the_viewer_in_ruler_mode(workspace: AnalyzeWorkspace):
    button = workspace._ruler_btn
    assert button is not None

    button.click()

    assert workspace._window.viewer.mode == Viewer.Mode.RULER
    assert button.isChecked()


def test_ruler_button_toggles_the_mode_off(workspace: AnalyzeWorkspace):
    button = workspace._ruler_btn
    assert button is not None

    button.click()
    button.click()

    assert workspace._window.viewer.mode == Viewer.Mode.NONE
    assert not button.isChecked()


def test_button_follows_a_mode_change_made_elsewhere(workspace: AnalyzeWorkspace):
    viewer = workspace._window.viewer
    button = workspace._ruler_btn
    assert button is not None

    viewer.select_mode(Viewer.Mode.RULER)
    assert button.isChecked()

    viewer.select_mode(Viewer.Mode.NONE)
    assert not button.isChecked()


def test_leaving_the_workspace_leaves_ruler_mode(workspace: AnalyzeWorkspace):
    viewer = workspace._window.viewer
    viewer.select_mode(Viewer.Mode.RULER)

    workspace.on_deactivated()

    assert viewer.mode == Viewer.Mode.NONE


def test_marker_button_adds_markers_by_clicking_in_viewer(
    workspace: AnalyzeWorkspace,
):
    viewer = workspace._window.viewer
    button = workspace._marker_btn
    assert button is not None

    button.click()
    assert viewer.mode == Viewer.Mode.MARKER
    assert button.isChecked()

    viewport = viewer.viewport()
    assert viewport is not None
    # PyQt6's stubs omit the QWidget overload supported by QTest at runtime.
    getattr(QTest, "mouseClick")(
        viewport,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(100, 100),
    )

    assert len(viewer.markers) == 1


def test_marker_and_ruler_buttons_are_mutually_exclusive(
    workspace: AnalyzeWorkspace,
):
    marker_button = workspace._marker_btn
    ruler_button = workspace._ruler_btn
    assert marker_button is not None
    assert ruler_button is not None

    marker_button.click()
    ruler_button.click()

    assert workspace._window.viewer.mode == Viewer.Mode.RULER
    assert ruler_button.isChecked()
    assert not marker_button.isChecked()
