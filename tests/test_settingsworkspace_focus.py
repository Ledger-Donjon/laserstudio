"""Autofocus (Delaunay triangulation) and Magic focus panels in the
redesigned Settings / Focus tools workspace."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QPushButton

from laserstudio.instruments.focus import FocusInstrument
from laserstudio.instruments.stage import Vector
from laserstudio.widgets.workspace.settingsworkspace import SettingsWorkspace
from laserstudio.widgets.workspace.settingsworkspace._autofocus import _AutofocusSection
from laserstudio.widgets.workspace.settingsworkspace._magic_focus import _MagicFocusSection


class _DummyStage(QObject):
    position_changed = pyqtSignal(Vector)

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        super().__init__()
        self._position = Vector(x, y, z)
        self.backlashes: list[float] | None = None
        self.moves: list[Vector] = []

    @property
    def position(self) -> Vector:
        return self._position

    def move_to(self, position: Vector, wait: bool = True, backlash: bool = False) -> None:
        self._position = position
        self.moves.append(position)
        self.position_changed.emit(position)


class _DummyCamera(QObject):
    new_image = pyqtSignal(object)

    def __init__(self, objective: float = 1.0) -> None:
        super().__init__()
        self.objective = objective
        self.laplacian_std_dev = 0.0


class _DummyInstruments:
    def __init__(self, stage: _DummyStage, camera: _DummyCamera, focus_helper: FocusInstrument):
        self.stage = stage
        self.camera = camera
        self.focus_helper = focus_helper


class _DummyWindow:
    def __init__(self, instruments: _DummyInstruments) -> None:
        self.instruments = instruments


@pytest.fixture(scope="module")
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def _make_window(x: float = 0.0, y: float = 0.0, z: float = 0.0) -> tuple[_DummyWindow, _DummyStage, _DummyCamera, FocusInstrument]:
    stage = _DummyStage(x, y, z)
    camera = _DummyCamera()
    focus_helper = FocusInstrument({}, camera, stage)  # type: ignore[arg-type]
    window = _DummyWindow(_DummyInstruments(stage, camera, focus_helper))
    return window, stage, camera, focus_helper


def _plane(x: float, y: float) -> float:
    return 5.0 + 0.1 * x + 0.1 * y


def _register_triangle(stage: _DummyStage, focus_helper: FocusInstrument, section: _AutofocusSection) -> None:
    register_btn = next(
        b for b in section.findChildren(QPushButton) if b.text() == "Register current position"
    )
    for x, y in [(0.0, 0.0), (20.0, 0.0), (0.0, 20.0)]:
        stage.move_to(Vector(x, y, _plane(x, y)))
        register_btn.click()


def test_autofocus_section_starts_empty_and_disabled(app: QApplication) -> None:
    window, _stage, _camera, _focus = _make_window()
    section = _AutofocusSection(window)

    assert section._count_lbl.text() == "0 points"
    assert not section._apply_btn.isEnabled()
    assert "3 points" in section._coverage_lbl.text() or "0 registered" in section._coverage_lbl.text()


def test_autofocus_register_covers_position_and_enables_apply(app: QApplication) -> None:
    window, stage, _camera, focus_helper = _make_window()
    section = _AutofocusSection(window)

    _register_triangle(stage, focus_helper, section)
    assert len(focus_helper.autofocus_helper) == 3
    assert section._count_lbl.text() == "3 points"

    # Move inside the triangle: apply is enabled, position is exactly covered.
    stage.move_to(Vector(5.0, 5.0, 0.0))
    assert focus_helper.can_autofocus_at(5.0, 5.0)
    assert focus_helper.is_autofocus_exact_at(5.0, 5.0)
    assert section._apply_btn.isEnabled()

    # Move outside the triangle: apply stays enabled (extrapolates from the
    # nearest triangle instead of refusing), but is no longer exact.
    stage.move_to(Vector(500.0, 500.0, 0.0))
    assert focus_helper.can_autofocus_at(500.0, 500.0)
    assert not focus_helper.is_autofocus_exact_at(500.0, 500.0)
    assert section._apply_btn.isEnabled()
    assert "extrapolate" in section._coverage_lbl.text()


def test_autofocus_disabled_without_enough_points(app: QApplication) -> None:
    window, stage, _camera, focus_helper = _make_window()
    section = _AutofocusSection(window)

    assert not section._apply_btn.isEnabled()
    register_btn = next(
        b for b in section.findChildren(QPushButton) if b.text() == "Register current position"
    )
    stage.move_to(Vector(0.0, 0.0, 1.0))
    register_btn.click()
    stage.move_to(Vector(10.0, 0.0, 1.0))
    register_btn.click()
    assert not section._apply_btn.isEnabled()
    assert "2 registered" in section._coverage_lbl.text()


def test_autofocus_apply_moves_stage_to_interpolated_z(app: QApplication) -> None:
    window, stage, _camera, focus_helper = _make_window()
    section = _AutofocusSection(window)
    _register_triangle(stage, focus_helper, section)

    stage.move_to(Vector(5.0, 5.0, 0.0))
    stage.moves.clear()
    section._apply_btn.click()

    assert stage.moves, "Apply autofocus should have moved the stage"
    final = stage.moves[-1]
    assert final.z == pytest.approx(_plane(5.0, 5.0))


def test_autofocus_remove_row_updates_points_and_rows(app: QApplication) -> None:
    window, stage, _camera, focus_helper = _make_window()
    section = _AutofocusSection(window)
    _register_triangle(stage, focus_helper, section)
    assert len(section._row_widgets) == 3

    # Delete-button of each row is its second child QPushButton (label has none).
    trash_buttons = [
        btn for row in section._row_widgets for btn in row.findChildren(QPushButton)
    ]
    trash_buttons[0].click()

    assert len(focus_helper.autofocus_helper) == 2
    assert len(section._row_widgets) == 2
    assert section._count_lbl.text() == "2 points"


def test_autofocus_clear_all_empties_points(app: QApplication) -> None:
    window, stage, _camera, focus_helper = _make_window()
    section = _AutofocusSection(window)
    _register_triangle(stage, focus_helper, section)

    clear_btn = next(
        b for b in section.findChildren(QPushButton) if "Clear all" in b.text()
    )
    clear_btn.click()

    assert len(focus_helper.autofocus_helper) == 0
    assert len(section._row_widgets) == 0
    assert section._count_lbl.text() == "0 points"


def test_magic_focus_section_shows_default_coarse_settings(app: QApplication) -> None:
    window, _stage, _camera, focus_helper = _make_window()
    section = _MagicFocusSection(window)

    assert focus_helper.coarse_focus_settings is not None
    assert section._fine_group is None  # no fine pass configured by default


def test_magic_focus_fine_toggle_creates_and_clears_settings(app: QApplication) -> None:
    window, _stage, _camera, focus_helper = _make_window()
    section = _MagicFocusSection(window)

    section._fine_toggle.setChecked(True)
    assert focus_helper.fine_focus_settings is not None
    assert section._fine_group is not None

    section._fine_toggle.setChecked(False)
    assert focus_helper.fine_focus_settings is None
    assert section._fine_group is None


def test_magic_focus_tracks_sharpness_readout(app: QApplication) -> None:
    window, _stage, camera, _focus_helper = _make_window()
    section = _MagicFocusSection(window)

    camera.laplacian_std_dev = 42.5
    camera.new_image.emit(None)
    assert section._sharpness_lbl.text() == "42.50"


def test_settings_workspace_build_focus_panel_wires_both_sections(app: QApplication) -> None:
    window, _stage, _camera, _focus_helper = _make_window()
    workspace = SettingsWorkspace(window)

    panel = workspace._build_focus_panel()
    assert panel.findChild(_AutofocusSection) is not None
    assert panel.findChild(_MagicFocusSection) is not None


def test_settings_workspace_build_focus_panel_handles_missing_focus_helper(
    app: QApplication,
) -> None:
    window, stage, camera, _focus_helper = _make_window()
    window.instruments.focus_helper = None
    workspace = SettingsWorkspace(window)

    panel = workspace._build_focus_panel()
    assert panel.findChild(_AutofocusSection) is None
    assert panel.findChild(_MagicFocusSection) is None
