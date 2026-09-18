"""Camera sections (image adjustment, generic controls, NIT) added to the
redesigned Settings / Camera workspace."""

from __future__ import annotations

import pickle
from typing import Any

import numpy
import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QFileDialog, QPushButton

from laserstudio.instruments.camera import CameraInstrument
from laserstudio.instruments.camera_nit import CameraNITInstrument
from laserstudio.instruments.camera_usb import CameraUSBInstrument
from laserstudio.widgets.toolbars.cameradockwidget import _resolution_label
from laserstudio.widgets.workspace.settingsworkspace._camera_generic import (
    _CameraGenericSection,
)
from laserstudio.widgets.workspace.settingsworkspace._camera_image_adjustment import (
    _CameraImageAdjustmentSection,
)
from laserstudio.widgets.workspace.settingsworkspace._camera_nit import (
    _CameraNITSection,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


# ── _CameraImageAdjustmentSection ────────────────────────────────────────────


class _DummyLevelsCamera(QObject):
    new_image = pyqtSignal(object)
    parameter_changed = pyqtSignal(str, object)

    def __init__(self, black: float = 0.0, white: float = 1.0) -> None:
        super().__init__()
        self.black_level = black
        self.white_level = white
        self._frame = numpy.zeros((8, 8), dtype=numpy.uint8)
        self.autoset_return: tuple[float, float] = (0.1, 0.9)

    @property
    def last_frame(self) -> numpy.ndarray:
        return self._frame

    def compute_histogram(self, frame: numpy.ndarray, width: int = -1):
        return numpy.histogram(frame, bins=max(1, width), range=(0, 255))

    def levels_autoset(self) -> tuple[float, float]:
        black, white = self.autoset_return
        self.black_level = black
        self.white_level = white
        self.parameter_changed.emit("black_level", black)
        self.parameter_changed.emit("white_level", white)
        return black, white


def test_image_adjustment_builds_and_refreshes_histogram(app: QApplication) -> None:
    camera = _DummyLevelsCamera()
    section = _CameraImageAdjustmentSection(camera)  # type: ignore[arg-type]

    assert section._bar_series.count() == 1
    # A new image must refresh the histogram without raising.
    camera.new_image.emit(None)
    assert section._bar_series.count() == 1


def test_image_adjustment_sliders_command_the_camera(app: QApplication) -> None:
    camera = _DummyLevelsCamera(0.1, 0.8)
    section = _CameraImageAdjustmentSection(camera)  # type: ignore[arg-type]

    assert section._black_slider._slider.value() == 100
    assert section._white_slider._slider.value() == 800

    section._black_slider._slider.setValue(250)
    assert camera.black_level == pytest.approx(0.25)

    section._white_slider._slider.setValue(950)
    assert camera.white_level == pytest.approx(0.95)


def test_image_adjustment_tracks_parameter_changed(app: QApplication) -> None:
    camera = _DummyLevelsCamera()
    section = _CameraImageAdjustmentSection(camera)  # type: ignore[arg-type]

    camera.parameter_changed.emit("black_level", 0.42)
    assert section._black_slider._slider.value() == 420

    camera.parameter_changed.emit("white_level", 0.77)
    assert section._white_slider._slider.value() == 770


def test_image_adjustment_auto_levels_button(app: QApplication) -> None:
    camera = _DummyLevelsCamera(0.0, 1.0)
    camera.autoset_return = (0.2, 0.6)
    section = _CameraImageAdjustmentSection(camera)  # type: ignore[arg-type]

    button = next(
        b for b in section.findChildren(QPushButton) if b.text() == "Auto levels"
    )
    button.click()

    assert camera.black_level == pytest.approx(0.2)
    assert camera.white_level == pytest.approx(0.6)
    assert section._black_slider._slider.value() == 200
    assert section._white_slider._slider.value() == 600


# ── _CameraGenericSection ────────────────────────────────────────────────────


class _DummyUSBCamera(CameraUSBInstrument):
    """A USB camera stand-in that skips the real OpenCV device setup, so the
    resolution combo box can be exercised without actual hardware."""

    def __init__(self, config: dict[str, Any]) -> None:
        CameraInstrument.__init__(self, config)  # type: ignore[misc]
        self._supported_resolutions = [(320, 240), (640, 480)]
        self.width = 320
        self.height = 240

    def set_resolution(self, width: int, height: int) -> tuple[int, int]:
        return CameraInstrument.set_resolution(self, width, height)

    def __del__(self) -> None:
        # No real cv2.VideoCapture was ever opened; skip CameraUSBInstrument's
        # teardown, which would otherwise try to release it.
        pass


class _DummyInstruments:
    def __init__(
        self, probes: list[Any] | None = None, lasers: list[Any] | None = None
    ) -> None:
        self.probes = probes or []
        self.lasers = lasers or []


class _DummyLaserStudio:
    def __init__(self, instruments: _DummyInstruments) -> None:
        self.instruments = instruments


def test_generic_section_without_context_disables_optional_controls(
    app: QApplication,
) -> None:
    camera = CameraInstrument({})
    section = _CameraGenericSection(camera, None)

    assert not section._show_hide_btn.isEnabled()
    assert section._resolution_combo is None
    assert not section._distortion_btn.isEnabled()
    assert section._probes_btn.isHidden()


def test_generic_section_refresh_interval_applies_on_enter(app: QApplication) -> None:
    camera = CameraInstrument({})
    section = _CameraGenericSection(camera, None)

    section._refresh_spin.setValue(999)
    section._refresh_spin.returnPressed2.emit()
    assert camera.refresh_interval == 999


def test_generic_section_resolution_combo_round_trip(app: QApplication) -> None:
    camera = _DummyUSBCamera({})
    section = _CameraGenericSection(camera, None)

    combo = section._resolution_combo
    assert combo is not None
    assert combo.count() == 2

    index_640 = combo.findText(_resolution_label(640, 480))
    assert index_640 != -1
    combo.setCurrentIndex(index_640)
    assert (camera.width, camera.height) == (640, 480)

    # Instrument -> widget: an external resolution change (e.g. settings load)
    # must be reflected back on the combo box.
    camera.parameter_changed.emit("resolution", [320, 240])
    assert combo.currentData() == (320, 240)


def test_generic_section_probes_wizard_visibility_follows_instruments(
    app: QApplication,
) -> None:
    camera = CameraInstrument({})

    no_probes = _DummyLaserStudio(_DummyInstruments())
    section = _CameraGenericSection(camera, None, no_probes)
    assert section._probes_btn.isHidden()
    assert section._distortion_btn.isEnabled()

    with_probes = _DummyLaserStudio(_DummyInstruments(probes=[object()]))
    section2 = _CameraGenericSection(camera, None, with_probes)
    assert not section2._probes_btn.isHidden()


# ── _CameraNITSection ────────────────────────────────────────────────────────


class _DummyNITCamera(QObject):
    parameter_changed = pyqtSignal(str, object)

    def __init__(self) -> None:
        super().__init__()
        self._gain = (10.0, 20.0)
        self._averaging = 4
        self.objective = 20.0
        self.shade_correction = numpy.zeros((4, 4), dtype=numpy.float32)
        self.autoset_gain: tuple[float, float] = (30.0, 40.0)
        self.shade_correct_calls = 0
        self.clear_shade_calls = 0

    @property
    def gain(self) -> tuple[float, float]:
        return self._gain

    @gain.setter
    def gain(self, value: tuple[float, float]) -> None:
        self._gain = value

    @property
    def averaging(self) -> int:
        return self._averaging

    @averaging.setter
    def averaging(self, value: int) -> None:
        self._averaging = value

    def gain_autoset(self) -> tuple[float, float]:
        self._gain = self.autoset_gain
        return self._gain

    def shade_correct(self) -> None:
        self.shade_correct_calls += 1

    def clear_shade_correction(self) -> None:
        self.clear_shade_calls += 1


def test_nit_section_builds_and_reads_initial_state(app: QApplication) -> None:
    camera = _DummyNITCamera()
    section = _CameraNITSection(camera)

    assert section._gain_low.value() == pytest.approx(10.0)
    assert section._gain_high.value() == pytest.approx(20.0)
    assert section._averaging_spin.value() == 4


def test_nit_section_gain_fields_command_the_camera(app: QApplication) -> None:
    camera = _DummyNITCamera()
    section = _CameraNITSection(camera)

    section._gain_low.setValue(100.0)
    section._gain_high.setValue(200.0)
    section._gain_low.returnPressed2.emit()
    assert camera.gain == (100.0, 200.0)

    # Low > high must be swapped before being applied.
    section._gain_low.setValue(500.0)
    section._gain_high.setValue(300.0)
    section._gain_high.returnPressed2.emit()
    assert camera.gain == (300.0, 500.0)
    assert section._gain_low.value() == pytest.approx(300.0)
    assert section._gain_high.value() == pytest.approx(500.0)


def test_nit_section_averaging_field_commands_the_camera(app: QApplication) -> None:
    camera = _DummyNITCamera()
    section = _CameraNITSection(camera)

    section._averaging_spin.setValue(9)
    section._averaging_spin.returnPressed2.emit()
    assert camera.averaging == 9


def test_nit_section_tracks_parameter_changed(app: QApplication) -> None:
    camera = _DummyNITCamera()
    section = _CameraNITSection(camera)

    camera.parameter_changed.emit("gain", [50.0, 60.0])
    assert section._gain_low.value() == pytest.approx(50.0)
    assert section._gain_high.value() == pytest.approx(60.0)

    camera.parameter_changed.emit("averaging", 7)
    assert section._averaging_spin.value() == 7


def test_nit_section_agc_toggle_drives_the_timer_and_gain(app: QApplication) -> None:
    camera = _DummyNITCamera()
    section = _CameraNITSection(camera)

    section._agc_btn.click()
    assert camera.gain == camera.autoset_gain
    assert section._gain_low.value() == pytest.approx(camera.autoset_gain[0])
    assert section._gain_high.value() == pytest.approx(camera.autoset_gain[1])
    assert section._agc_timer.isActive()

    section._agc_btn.click()
    assert not section._agc_timer.isActive()


def test_nit_section_shade_buttons_call_the_camera(app: QApplication) -> None:
    camera = _DummyNITCamera()
    section = _CameraNITSection(camera)

    shade_btn = next(
        b for b in section.findChildren(QPushButton) if b.text() == "Shade"
    )
    clear_btn = next(
        b for b in section.findChildren(QPushButton) if b.text() == "Clear"
    )
    shade_btn.click()
    clear_btn.click()
    assert camera.shade_correct_calls == 1
    assert camera.clear_shade_calls == 1


def test_nit_section_shade_save_and_load_round_trip(
    app: QApplication, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    camera = _DummyNITCamera()
    section = _CameraNITSection(camera)
    path = tmp_path / "shade.pickle"

    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(path), "")),
    )
    save_btn = next(
        b for b in section.findChildren(QPushButton) if b.text() == "Save"
    )
    save_btn.click()

    assert path.exists()
    with open(path, "rb") as f:
        saved = pickle.load(f)
    assert numpy.array_equal(saved, camera.shade_correction)

    # Change the in-memory correction, then load it back from disk.
    camera.shade_correction = numpy.ones((4, 4), dtype=numpy.float32)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(path), "")),
    )
    load_btn = next(
        b for b in section.findChildren(QPushButton) if b.text() == "Load"
    )
    load_btn.click()
    assert numpy.array_equal(camera.shade_correction, saved)


# ── Full SettingsWorkspace wiring ────────────────────────────────────────────


class _WiringInstruments:
    def __init__(self, camera: CameraInstrument) -> None:
        self.camera = camera
        self.light = None


class _WiringWindow:
    def __init__(self, camera: CameraInstrument) -> None:
        self.instruments = _WiringInstruments(camera)
        self.viewer = None


def test_settings_workspace_build_camera_panel_wires_new_sections(
    app: QApplication,
) -> None:
    from laserstudio.widgets.workspace.settingsworkspace import SettingsWorkspace

    camera = CameraInstrument({})
    workspace = SettingsWorkspace(_WiringWindow(camera))  # type: ignore[arg-type]

    panel = workspace._build_camera_panel()
    assert panel.findChild(_CameraImageAdjustmentSection) is not None
    assert panel.findChild(_CameraGenericSection) is not None
    # A plain CameraInstrument is neither USB nor NIT: no NIT section expected.
    assert panel.findChild(_CameraNITSection) is None


class _MinimalNITStandIn(CameraNITInstrument):
    """A real ``CameraNITInstrument`` (so isinstance checks pass) that never
    touches ``self.pynit``, to test the isinstance-gated wiring in
    ``_build_camera_panel`` without the private pynit driver."""

    def __init__(self) -> None:
        CameraInstrument.__init__(self, {})  # type: ignore[misc]

    @property
    def gain(self) -> tuple[float, float]:
        return (0.0, 0.0)

    @gain.setter
    def gain(self, value: tuple[float, float]) -> None:
        pass

    @property
    def averaging(self) -> int:
        return 1

    @averaging.setter
    def averaging(self, value: int) -> None:
        pass

    @property
    def shade_correction(self) -> numpy.ndarray:
        return numpy.zeros((1, 1), dtype=numpy.float32)

    @shade_correction.setter
    def shade_correction(self, value: numpy.ndarray) -> None:
        pass

    def gain_autoset(self) -> tuple[float, float]:
        return (0.0, 0.0)

    def shade_correct(self) -> None:
        pass

    def clear_shade_correction(self) -> None:
        pass


def test_settings_workspace_build_camera_panel_adds_nit_section(
    app: QApplication,
) -> None:
    from laserstudio.widgets.workspace.settingsworkspace import SettingsWorkspace

    camera = _MinimalNITStandIn()
    workspace = SettingsWorkspace(_WiringWindow(camera))  # type: ignore[arg-type]

    panel = workspace._build_camera_panel()
    assert panel.findChild(_CameraNITSection) is not None
