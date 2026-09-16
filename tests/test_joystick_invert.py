"""Analog joystick handling for PI stages, from the Positioning settings panel.

A Mercury controller rejects motion commands on an axis held by the joystick,
so the instrument turns it off before commanding a move; the tests below cover
both that and the per-axis direction inversion.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication

from laserstudio.instruments.stage import Vector
from laserstudio.instruments.stage_pi import PIStageInstrument
from laserstudio.widgets.newui.viewer_hud import ViewerHudControls
from laserstudio.widgets.viewer import Viewer
from laserstudio.widgets.workspace.settingsworkspace import _JoystickControls


class _Mutex:
    def lock(self) -> None:
        return None

    def unlock(self) -> None:
        return None


class _FakePI:
    num_axis = 3
    addresses = [1, 2, 3]

    def __init__(self) -> None:
        self._joystick_enabled = [False, False, False]
        self._joystick_buttons = [False, False, False]
        self.joystick_direction_inverted = [False, False, False]
        self.velocity = [1.0, 1.0, 1.0]
        self.velocity_max = [4.0, 4.0, 4.0]
        self.acceleration = [10.0, 10.0, 10.0]
        self.deceleration = [10.0, 10.0, 10.0]
        self.position = Vector(0.0, 0.0, 0.0)
        self.moves: list[list[float]] = []

    @property
    def joystick_enabled(self) -> list[bool]:
        return list(self._joystick_enabled)

    @joystick_enabled.setter
    def joystick_enabled(self, value: bool | list[bool]) -> None:
        # Like the controller: a single flag applies to every address.
        if isinstance(value, bool):
            value = [value] * len(self.addresses)
        self._joystick_enabled = [bool(v) for v in value]

    @property
    def joystick_buttons(self) -> list[bool]:
        return list(self._joystick_buttons)

    def move_to(self, position: Vector, wait: bool = False) -> None:
        if any(self.joystick_enabled):
            # What the real controller does: the command is simply ignored.
            return
        self.position = Vector(*position.data)
        self.moves.append(list(position.data))


class _ToggleDevice:
    def __init__(self, on: bool = False) -> None:
        self.on_off = on
        self.light = on


class _FocusThread:
    def __init__(self) -> None:
        self.started = False

    def isRunning(self) -> bool:
        return self.started

    def start(self) -> None:
        self.started = True


class _FocusHelper:
    def __init__(self) -> None:
        self.thread = _FocusThread()

    def magic_focus(self) -> _FocusThread:
        return self.thread


def _stub_pi() -> PIStageInstrument:
    instrument = PIStageInstrument.__new__(PIStageInstrument)
    # Skipping __init__ skips the serial connection, but the QObject half still
    # has to exist for the instrument's signals to work.
    QObject.__init__(instrument)
    instrument.mutex = _Mutex()  # type: ignore[assignment]
    instrument.stage = _FakePI()  # type: ignore[assignment]
    instrument._pi_joystick_button_states = None
    instrument._pi_joystick_button_poll_failed = False
    return instrument


def _movable_stub_pi() -> tuple[PIStageInstrument, _FakePI]:
    """A stub with the geometry and guardrails a move goes through.

    The controller is returned alongside the instrument: the moves it received
    are what the tests assert on.
    """
    instrument = _stub_pi()
    instrument.unit_factors = [1.0, 1.0, 1.0]
    instrument.offset_origin = [0.0, 0.0, 0.0]
    instrument.shear = [0.0, 0.0]
    instrument.backlashes = []
    instrument._guardrail_enabled = False
    instrument._soft_limits_enabled = False
    instrument._last_reported_alarm = None
    instrument._pi_saved_motion_params = None
    controller = instrument.stage
    assert isinstance(controller, _FakePI)
    return instrument, controller


@pytest.fixture(scope="module")
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def test_invert_one_axis_updates_the_controller():
    instrument = _stub_pi()

    instrument.set_pi_joystick_invert_axis(1, True)

    assert instrument.pi_joystick_direction_inverted == [False, True, False]


def test_invert_from_settings_round_trip():
    instrument = _stub_pi()

    instrument.pi_joystick_direction_inverted = [True, False, True]

    assert instrument.pi_joystick_direction_inverted == [True, False, True]


def test_a_move_turns_the_joystick_off_and_goes_through():
    instrument, controller = _movable_stub_pi()
    instrument.pi_joystick_enabled = True

    instrument.move_to(Vector(10.0, 20.0, 30.0), wait=False)

    assert instrument.pi_joystick_enabled == [False, False, False]
    assert controller.moves == [[10.0, 20.0, 30.0]]


def test_a_move_leaves_an_already_disabled_joystick_alone():
    instrument, controller = _movable_stub_pi()
    instrument.pi_joystick_enabled = False
    states = instrument.pi_joystick_enabled

    instrument.move_to(Vector(1.0, 2.0, 3.0), wait=False)

    assert instrument.pi_joystick_enabled == states
    assert controller.moves == [[1.0, 2.0, 3.0]]


def test_the_panel_follows_the_joystick_turned_off_by_a_move(app: QApplication):
    instrument, _ = _movable_stub_pi()
    panel = _JoystickControls(instrument)
    panel._axis_buttons[1].click()
    assert instrument.pi_joystick_enabled[1]

    instrument.move_to(Vector(5.0, 5.0, 5.0), wait=False)

    assert all(not button.isChecked() for button in panel._axis_buttons)


def test_positioning_panel_invert_buttons_drive_the_stage(app: QApplication):
    instrument = _stub_pi()
    panel = _JoystickControls(instrument)

    assert len(panel._invert_buttons) == 3
    assert all(not button.isChecked() for button in panel._invert_buttons)

    panel._invert_buttons[2].click()

    assert instrument.pi_joystick_direction_inverted == [False, False, True]
    assert panel._invert_buttons[2].isChecked()
    assert not panel._invert_buttons[0].isChecked()


def test_pi_joystick_button_emits_press_and_release_edges():
    instrument = _stub_pi()
    controller = instrument.stage
    assert isinstance(controller, _FakePI)
    pressed: list[int] = []
    released: list[int] = []
    instrument.joystick_button_pressed.connect(pressed.append)
    instrument.joystick_button_released.connect(released.append)

    # The initial poll is a baseline, even if a button was already held.
    controller._joystick_buttons = [True, False, False]
    instrument.poll_pi_joystick_buttons()
    assert pressed == []
    assert released == []

    controller._joystick_buttons = [True, True, False]
    instrument.poll_pi_joystick_buttons()
    instrument.poll_pi_joystick_buttons()  # No duplicate while still held.
    controller._joystick_buttons = [False, True, False]
    instrument.poll_pi_joystick_buttons()

    assert pressed == [1]
    assert released == [0]


def _press(instrument: PIStageInstrument, button: int) -> None:
    controller = instrument.stage
    assert isinstance(controller, _FakePI)
    controller._joystick_buttons[button] = True
    instrument.poll_pi_joystick_buttons()
    controller._joystick_buttons[button] = False
    instrument.poll_pi_joystick_buttons()


def test_pi_buttons_latch_the_velocity_they_change():
    instrument = _stub_pi()
    instrument.poll_pi_joystick_buttons()

    _press(instrument, 0)
    assert instrument.pi_velocity_mm_s == [2.0, 2.0, 2.0]

    # The doubled speed stays in effect once the button is released.
    _press(instrument, 0)
    assert instrument.pi_velocity_mm_s == [4.0, 4.0, 4.0]

    _press(instrument, 1)
    assert instrument.pi_velocity_mm_s == [2.0, 2.0, 2.0]

    _press(instrument, 1)
    _press(instrument, 1)
    assert instrument.pi_velocity_mm_s == [0.5, 0.5, 0.5]


def test_pi_velocity_stays_within_what_the_controller_accepts():
    instrument = _stub_pi()
    instrument.poll_pi_joystick_buttons()

    for _ in range(5):
        _press(instrument, 0)
    assert instrument.pi_velocity_mm_s == [4.0, 4.0, 4.0]  # velocity_max

    for _ in range(20):
        _press(instrument, 1)
    assert instrument.pi_velocity_mm_s == [
        PIStageInstrument.MIN_BUTTON_VELOCITY_MM_S
    ] * 3


def test_pi_button_two_emits_the_action_signal_once_per_press():
    instrument = _stub_pi()
    controller = instrument.stage
    assert isinstance(controller, _FakePI)
    actions: list[bool] = []
    instrument.joystick_action_button_pressed.connect(lambda: actions.append(True))
    instrument.poll_pi_joystick_buttons()

    controller._joystick_buttons[2] = True
    instrument.poll_pi_joystick_buttons()
    instrument.poll_pi_joystick_buttons()
    controller._joystick_buttons[2] = False
    instrument.poll_pi_joystick_buttons()

    assert actions == [True]


def test_hud_executes_the_action_selected_for_button_two(app: QApplication):
    instrument = _stub_pi()
    laser_a = _ToggleDevice()
    laser_b = _ToggleDevice()
    light = _ToggleDevice()
    focus = _FocusHelper()
    instruments = SimpleNamespace(
        stage=instrument,
        lasers=[laser_a, laser_b],
        light=light,
        focus_helper=focus,
    )
    controls = ViewerHudControls(
        Viewer(),
        instruments,  # type: ignore[arg-type]
    )

    controls._selected_action = "toggle_laser"
    instrument.joystick_action_button_pressed.emit()
    assert laser_a.on_off and laser_b.on_off
    instrument.joystick_action_button_pressed.emit()
    assert not laser_a.on_off and not laser_b.on_off

    controls._selected_action = "toggle_light"
    instrument.joystick_action_button_pressed.emit()
    assert light.light

    controls._selected_action = "toggle_joystick"
    instrument.joystick_action_button_pressed.emit()
    assert instrument.pi_joystick_enabled == [True, True, True]

    controls._selected_action = "magic_focus"
    instrument.joystick_action_button_pressed.emit()
    assert focus.thread.started
