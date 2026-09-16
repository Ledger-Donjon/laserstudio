"""Probe/laser spot calibration from the redesigned Settings workspace."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QObject, QPointF, pyqtSignal
from PyQt6.QtWidgets import QApplication

from laserstudio.instruments.laser_dummy import LaserDummy
from laserstudio.instruments.probe import ProbeInstrument
from laserstudio.widgets.viewer import Viewer
from laserstudio.widgets.workspace.settingsworkspace import (
    _LaserSection,
    _ProbeOffsetControl,
    _ProbeSection,
)


class _Camera(QObject):
    new_image = pyqtSignal(object)
    parameter_changed = pyqtSignal(str, object)

    width = 100
    height = 80
    width_um = 20.0
    height_um = 16.0
    objective = 5.0
    is_average_valid = True


@pytest.fixture(scope="module")
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def _viewer_and_probe() -> tuple[Viewer, ProbeInstrument]:
    probe = ProbeInstrument({"label": "Laser spot"})
    viewer = Viewer()
    viewer.add_stage_sight(None, _Camera(), [probe])  # type: ignore[arg-type]
    assert viewer.stage_sight is not None
    viewer.stage_sight.setPos(QPointF(100.0, 200.0))
    return viewer, probe


def test_viewer_selects_probe_offset_relative_to_camera_centre(
    app: QApplication,
) -> None:
    viewer, probe = _viewer_and_probe()

    assert viewer.select_probe_offset(probe)
    assert viewer.mode == Viewer.Mode.PROBE_OFFSET
    assert viewer.probe_offset_target is probe

    # This scene point is (+4, -3) sample-plane µm from the camera centre.
    assert viewer._set_probe_offset_from_scene(QPointF(104.0, 197.0))
    assert probe.offset_pos == (20.0, -15.0)  # objective ×5, sensor-plane µm
    assert viewer.mode == Viewer.Mode.NONE
    assert viewer.probe_offset_target is None


def test_probe_offset_button_tracks_the_one_shot_viewer_mode(
    app: QApplication,
) -> None:
    viewer, probe = _viewer_and_probe()
    control = _ProbeOffsetControl(probe, viewer)

    control._button.click()
    assert control._button.isChecked()
    assert viewer.probe_offset_target is probe

    viewer._set_probe_offset_from_scene(QPointF(102.0, 201.0))
    assert not control._button.isChecked()
    assert "X +10.00" in control._value.text()
    assert "Y +5.00" in control._value.text()


def test_selecting_the_same_probe_again_cancels_calibration(
    app: QApplication,
) -> None:
    viewer, probe = _viewer_and_probe()

    assert viewer.select_probe_offset(probe)
    assert viewer.select_probe_offset(probe)
    assert viewer.mode == Viewer.Mode.NONE
    assert probe.offset_pos is None


def test_settings_exposes_calibration_for_probes_and_lasers(
    app: QApplication,
) -> None:
    viewer, probe = _viewer_and_probe()
    laser = LaserDummy({"label": "Laser"})

    probe_section = _ProbeSection(probe, 0, viewer)
    laser_section = _LaserSection(laser, 0, viewer)

    probe_control = probe_section.findChild(_ProbeOffsetControl)
    laser_control = laser_section.findChild(_ProbeOffsetControl)
    assert probe_control is not None and probe_control._button.isEnabled()
    assert laser_control is not None and laser_control._button.isEnabled()
