"""Optispot controls in the redesigned Settings / Lasers panel."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QPushButton, QSlider

from laserstudio.instruments.laser_dummy import LaserDummy
from laserstudio.instruments.stage import StageInstrument, Vector
from laserstudio.widgets.optispotcontrol import OPTISPOT_MAX, OptispotControl
from laserstudio.widgets.workspace.settingsworkspace import (
    _LaserSection,
    _OptispotSection,
)


class _DummyOptispot(QObject):
    position_changed = pyqtSignal(Vector)

    def __init__(self, x: float = 0.0) -> None:
        super().__init__()
        self._x = x

    @property
    def position(self) -> Vector:
        return Vector(self._x)

    def move_to(self, position: Vector, wait: bool, backlash: bool = False) -> None:
        self._x = float(position.x)
        self.position_changed.emit(Vector(self._x))


@pytest.fixture(scope="module")
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def test_optispot_tracks_position_changed_slider_and_spin(
    app: QApplication,
) -> None:
    stage = _DummyOptispot(42.4)
    section = _OptispotSection(stage)  # type: ignore[arg-type]

    assert section._spin.value() == pytest.approx(42.4)
    assert section._slider.value() == 42
    assert section._spin.maximum() == float(OPTISPOT_MAX) == 1000.0

    stage.move_to(Vector(123.6), wait=False)
    assert section._spin.value() == pytest.approx(123.6)
    assert section._slider.value() == 124


def test_optispot_plus_minus_slider_and_spin_command_the_stage(
    app: QApplication,
) -> None:
    stage = _DummyOptispot(10.0)
    section = _OptispotSection(stage)  # type: ignore[arg-type]

    buttons = section.findChildren(QPushButton)
    minus, plus = buttons[0], buttons[1]
    minus.click()
    assert stage._x == 9.0
    plus.click()
    plus.click()
    assert stage._x == 11.0

    section._slider.setValue(1000)
    assert stage._x == float(OPTISPOT_MAX)
    section._slider.setValue(0)
    assert stage._x == 0.0

    section._spin.setValue(250.5)
    assert stage._x == pytest.approx(250.5)
    assert section._slider.value() == 250


def test_single_axis_position_is_not_contaminated_by_shear() -> None:
    stage = StageInstrument.__new__(StageInstrument)
    stage.shear = [0.0, 0.0]
    stage.unit_factors = [1.0]
    stage.offset_origin = [0.0]

    position = stage._apply_position_transforms(Vector(37.0))
    assert position.x == 37.0


def test_optispot_ignores_an_unreadable_position(app: QApplication) -> None:
    stage = _DummyOptispot(12.0)
    section = _OptispotSection(stage)  # type: ignore[arg-type]

    section._on_position_changed(Vector(float("nan")))
    assert section._spin.value() == pytest.approx(12.0)
    assert section._last_position == 12.0


def test_laser_section_shows_optispot_when_present(app: QApplication) -> None:
    laser = LaserDummy({"label": "Laser"})
    laser.optispot = _DummyOptispot(7.0)  # type: ignore[assignment]
    section = _LaserSection(laser, 0, None)
    assert section.findChild(_OptispotSection) is not None
    assert section.findChild(QSlider) is not None


def test_laser_section_hides_optispot_when_absent(app: QApplication) -> None:
    laser = LaserDummy({"label": "Laser"})
    section = _LaserSection(laser, 0, None)
    assert section.findChild(_OptispotSection) is None


def test_classic_control_tracks_and_commands_the_stage(app: QApplication) -> None:
    stage = _DummyOptispot(42.4)
    control = OptispotControl(stage)  # type: ignore[arg-type]

    assert control.position_input.value() == pytest.approx(42.4)
    assert control.slider.value() == 42

    stage.move_to(Vector(123.6), wait=False)
    assert control.position_input.value() == pytest.approx(123.6)
    assert control.slider.value() == 124

    control.move_by(-1)
    assert stage._x == pytest.approx(122.6)

    control.position_input.setValue(250.5)
    assert stage._x == pytest.approx(250.5)

    control.slider.setValue(1000)
    assert stage._x == float(OPTISPOT_MAX)


def test_classic_control_clamps_and_ignores_an_unreadable_position(
    app: QApplication,
) -> None:
    stage = _DummyOptispot(5.0)
    control = OptispotControl(stage)  # type: ignore[arg-type]

    control.move_to(-10.0)
    assert stage._x == 0.0
    control.move_to(5000.0)
    assert stage._x == float(OPTISPOT_MAX)

    control.update_position(Vector(float("nan")))
    assert control.last_position == float(OPTISPOT_MAX)
