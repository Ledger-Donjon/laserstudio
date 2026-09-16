import logging
from typing import Any, cast

from PyQt6.QtCore import QTimer, pyqtSignal
from pystages import PI

from ..utils.yaml_types import Config
from .stage import StageInstrument


class PIStageInstrument(StageInstrument):
    """Class to regroup PI stage instrument operations"""

    joystick_button_pressed = pyqtSignal(int)
    """Emitted with the zero-based PI joystick button index when pressed."""

    joystick_button_released = pyqtSignal(int)
    """Emitted with the zero-based PI joystick button index when released."""

    velocity_changed = pyqtSignal()
    """Emitted when the stage changed its own velocity, from a joystick button."""

    joystick_action_button_pressed = pyqtSignal()
    """Emitted when PI joystick button 2 is pressed."""

    # The base class picks the device from the configured type; declaring it
    # here just narrows it for this subclass (a property would shadow the
    # attribute the base constructor assigns).
    stage: PI

    #: Last joystick activation written to the controller, None until known.
    _pi_joystick_state: list[bool] | None = None

    #: Halving the speed must never leave the stage unable to move at all.
    MIN_BUTTON_VELOCITY_MM_S = 0.001

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        adresses = self.stage.addresses
        self._pi_joystick_velocity_mm_s = self._expand_per_axis_config(
            config.get("joystick_velocity_mm_s", [50.0, 50.0, 5.0]), len(adresses)
        )
        self._pi_joystick_acceleration_mm_s2 = self._expand_per_axis_config(
            config.get("joystick_acceleration_mm_s2", [400.0, 400.0, 40.0]),
            len(adresses),
        )
        self._pi_joystick_deceleration_mm_s2 = self._expand_per_axis_config(
            config.get("joystick_deceleration_mm_s2", [400.0, 400.0, 40.0]),
            len(adresses),
        )
        self._pi_saved_motion_params: (
            tuple[list[float], list[float], list[float]] | None
        ) = None
        self._apply_pi_motion_from_config(config, len(adresses))
        if "joystick_direction_inverted" in config:
            try:
                self.pi_joystick_direction_inverted = cast(
                    Any, config["joystick_direction_inverted"]
                )
            except Exception as exc:
                logging.getLogger("laserstudio").warning(
                    "Could not apply joystick direction inversion: %s", exc
                )
        self._pi_joystick_button_states: list[bool] | None = None
        self._pi_joystick_button_poll_failed = False
        self._pi_joystick_button_timer = QTimer(self)
        self._pi_joystick_button_timer.setInterval(
            max(10, int(config.get("joystick_button_poll_interval_ms", 100)))
        )
        self._pi_joystick_button_timer.timeout.connect(
            self.poll_pi_joystick_buttons
        )
        self._pi_joystick_button_timer.start()

    def poll_pi_joystick_buttons(self) -> None:
        """Read PI joystick buttons and emit press/release edges.

        The first successful read establishes a baseline so a button already
        held while Laser Studio starts is not reported as a new press.
        """
        self.mutex.lock()
        try:
            states = [bool(state) for state in self.stage.joystick_buttons]
        except Exception as exc:
            if not self._pi_joystick_button_poll_failed:
                logging.getLogger("laserstudio").warning(
                    "Could not read PI joystick buttons: %s", exc
                )
                self._pi_joystick_button_poll_failed = True
            return
        finally:
            self.mutex.unlock()

        self._pi_joystick_button_poll_failed = False
        previous = self._pi_joystick_button_states
        self._pi_joystick_button_states = states
        if previous is None:
            return

        for index, pressed in enumerate(states):
            was_pressed = previous[index] if index < len(previous) else False
            if pressed == was_pressed:
                continue
            if pressed:
                self._on_pi_joystick_button_pressed(index)
                self.joystick_button_pressed.emit(index)
            else:
                self.joystick_button_released.emit(index)

    def _on_pi_joystick_button_pressed(self, button: int) -> None:
        if button == 0:
            self._scale_pi_velocity(2.0)
        elif button == 1:
            self._scale_pi_velocity(0.5)
        elif button == 2:
            self.joystick_action_button_pressed.emit()

    def _scale_pi_velocity(self, factor: float) -> None:
        """Latch a new speed: each button press scales the current velocity.

        The new speed stays in effect once the button is released, so it is
        clamped to what the controller accepts on each axis.
        """
        try:
            velocities = self.pi_velocity_mm_s
            maxima = self.pi_velocity_max_mm_s
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                "Could not read the PI velocity to change it: %s", exc
            )
            return

        scaled: list[float] = []
        for axis, velocity in enumerate(velocities):
            value = max(velocity * factor, self.MIN_BUTTON_VELOCITY_MM_S)
            maximum = maxima[axis] if axis < len(maxima) else 0.0
            scaled.append(min(value, maximum) if maximum > 0.0 else value)

        try:
            self.pi_velocity_mm_s = scaled
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                "Could not change the PI velocity: %s", exc
            )
            return
        self.velocity_changed.emit()

    def home(self, wait: bool = False):
        """
        Home the stage.
        """
        super().home(wait=wait)
        errors = self.stage.error()
        if errors:
            logging.getLogger("laserstudio").error(f"Errors: {errors}")
        else:
            logging.getLogger("laserstudio").info("No errors")

    def _apply_pi_motion_from_config(self, config: dict[str, Any], count: int) -> None:
        """Apply optional closed-loop VEL/ACC/DEC from config at startup."""
        if "velocity_mm_s" in config:
            self.stage.velocity = self._expand_per_axis_config(
                config["velocity_mm_s"], count
            )
        if "acceleration_mm_s2" in config:
            self.stage.acceleration = self._expand_per_axis_config(
                config["acceleration_mm_s2"], count
            )
        if "deceleration_mm_s2" in config:
            self.stage.deceleration = self._expand_per_axis_config(
                config["deceleration_mm_s2"], count
            )

    @property
    def pi_velocity_mm_s(self) -> list[float]:
        """Closed-loop velocity (mm/s) for each PI controller axis."""
        self.mutex.lock()
        try:
            return list(self.stage.velocity)
        finally:
            self.mutex.unlock()

    @pi_velocity_mm_s.setter
    def pi_velocity_mm_s(self, value: float | list[float]) -> None:
        if isinstance(value, (int, float)):
            values = [float(value)] * self.stage.num_axis
        else:
            values = self._expand_per_axis_config(value, self.stage.num_axis)
        self.mutex.lock()
        try:
            self.stage.velocity = values
        finally:
            self.mutex.unlock()

    @property
    def pi_velocity_max_mm_s(self) -> list[float]:
        """Maximum settable closed-loop velocity (mm/s) per PI axis."""
        self.mutex.lock()
        try:
            return list(self.stage.velocity_max)
        finally:
            self.mutex.unlock()

    @property
    def pi_acceleration_max_mm_s2(self) -> list[float]:
        """Maximum settable closed-loop acceleration (mm/s²) per PI axis."""
        self.mutex.lock()
        try:
            return list(self.stage.acceleration_max)
        finally:
            self.mutex.unlock()

    @property
    def pi_deceleration_max_mm_s2(self) -> list[float]:
        """Maximum settable closed-loop deceleration (mm/s²) per PI axis."""
        self.mutex.lock()
        try:
            return list(self.stage.deceleration_max)
        finally:
            self.mutex.unlock()

    @property
    def pi_acceleration_mm_s2(self) -> list[float]:
        """Closed-loop acceleration (mm/s²) for each PI controller axis."""
        self.mutex.lock()
        try:
            return list(self.stage.acceleration)
        finally:
            self.mutex.unlock()

    @pi_acceleration_mm_s2.setter
    def pi_acceleration_mm_s2(self, value: float | list[float]) -> None:
        if isinstance(value, (int, float)):
            values = [float(value)] * self.stage.num_axis
        else:
            values = self._expand_per_axis_config(value, self.stage.num_axis)
        self.mutex.lock()
        try:
            self.stage.acceleration = values
        finally:
            self.mutex.unlock()

    @property
    def pi_deceleration_mm_s2(self) -> list[float]:
        """Closed-loop deceleration (mm/s²) for each PI controller axis."""
        self.mutex.lock()
        try:
            return list(self.stage.deceleration)
        finally:
            self.mutex.unlock()

    @pi_deceleration_mm_s2.setter
    def pi_deceleration_mm_s2(self, value: float | list[float]) -> None:
        if isinstance(value, (int, float)):
            values = [float(value)] * self.stage.num_axis
        else:
            values = self._expand_per_axis_config(value, self.stage.num_axis)
        self.mutex.lock()
        try:
            self.stage.deceleration = values
        finally:
            self.mutex.unlock()

    def set_pi_axis_motion(
        self,
        axis: int,
        *,
        velocity_mm_s: float | None = None,
        acceleration_mm_s2: float | None = None,
        deceleration_mm_s2: float | None = None,
    ) -> None:
        """Update VEL/ACC/DEC for a single PI axis."""
        if velocity_mm_s is not None:
            values = self.pi_velocity_mm_s
            values[axis] = float(velocity_mm_s)
            self.pi_velocity_mm_s = values
        if acceleration_mm_s2 is not None:
            values = self.pi_acceleration_mm_s2
            values[axis] = float(acceleration_mm_s2)
            self.pi_acceleration_mm_s2 = values
        if deceleration_mm_s2 is not None:
            values = self.pi_deceleration_mm_s2
            values[axis] = float(deceleration_mm_s2)
            self.pi_deceleration_mm_s2 = values

    @property
    def pi_joystick_enabled(self) -> list[bool]:
        """Joystick activation state for each PI controller axis."""
        self.mutex.lock()
        try:
            states = list(self.stage.joystick_enabled)
        finally:
            self.mutex.unlock()
        self._pi_joystick_state = list(states)
        return states

    @pi_joystick_enabled.setter
    def pi_joystick_enabled(self, value: bool | list[bool]) -> None:
        enabled = any(value) if isinstance(value, list) else value
        self.mutex.lock()
        try:
            if enabled:
                self._pi_saved_motion_params = (
                    self.stage.velocity,
                    self.stage.acceleration,
                    self.stage.deceleration,
                )
            elif self._pi_saved_motion_params is not None:
                self.stage.velocity = self._pi_saved_motion_params[0]
                self.stage.acceleration = self._pi_saved_motion_params[1]
                self.stage.deceleration = self._pi_saved_motion_params[2]
            self.stage.joystick_enabled = value
        finally:
            self.mutex.unlock()
        if isinstance(value, bool):
            self._pi_joystick_state = [value] * self.stage.num_axis
        else:
            self._pi_joystick_state = [bool(v) for v in value]
        self.joystick_changed.emit()

    def _release_joystick_for_move(self) -> None:
        """Turn the analog joystick off so the controller accepts the move.

        Mercury controllers reject motion commands on an axis held by the
        joystick, so a move requested while it is on would be silently
        dropped. The last state written is cached to keep the common case
        (joystick off) free of any serial round trip.
        """
        try:
            states = self._pi_joystick_state
            if states is None:
                states = self.pi_joystick_enabled
            if not any(states):
                return
            logging.getLogger("laserstudio").info(
                "Disabling the PI joystick, which would otherwise reject the move."
            )
            self.pi_joystick_enabled = False
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                "Could not disable the PI joystick before moving: %s", exc
            )

    def set_pi_joystick_axis(self, axis: int, enabled: bool) -> None:
        """Enable or disable the analog joystick on a single PI axis."""
        states = self.pi_joystick_enabled
        states[axis] = enabled
        self.pi_joystick_enabled = states

    @property
    def pi_joystick_direction_inverted(self) -> list[bool]:
        """Joystick motion polarity for each PI controller axis."""
        self.mutex.lock()
        try:
            return list(self.stage.joystick_direction_inverted)
        finally:
            self.mutex.unlock()

    @pi_joystick_direction_inverted.setter
    def pi_joystick_direction_inverted(self, value: bool | list[bool]) -> None:
        if isinstance(value, bool):
            values = [value] * self.stage.num_axis
        else:
            values = [bool(v) for v in value]
            if len(values) < self.stage.num_axis:
                values += [False] * (self.stage.num_axis - len(values))
            values = values[: self.stage.num_axis]
        self.mutex.lock()
        try:
            self.stage.joystick_direction_inverted = values
        finally:
            self.mutex.unlock()

    def set_pi_joystick_invert_axis(self, axis: int, inverted: bool) -> None:
        """Invert or restore joystick motion on a single PI axis."""
        states = self.pi_joystick_direction_inverted
        states[axis] = inverted
        self.pi_joystick_direction_inverted = states

    @property
    def supports_analog_joystick(self) -> bool:
        """PI/Mercury controllers drive an analog joystick, one axis at a time."""
        return True

    def enable_joystick(self, enabled: bool):
        """
        Enable the joystick on every axis of the stage.
        """
        self.pi_joystick_enabled = enabled

    def reboot(self):
        """
        Reboot the stage.
        """
        # Send command RBT
        for a in self.stage.addresses:
            self.stage.send(a, "RBT")

    @staticmethod
    def _expand_per_axis_config(value: float | list[float], count: int) -> list[float]:
        """Expand a scalar or list config value to one entry per axis."""
        if isinstance(value, (int, float)):
            return [float(value)] * count
        values = [float(v) for v in value]
        if len(values) < count:
            values += [values[-1]] * (count - len(values))
        return values[:count]

    @property
    def settings(self) -> Config:
        super_settings = super().settings
        super_settings["velocity_mm_s"] = self.pi_velocity_mm_s
        super_settings["acceleration_mm_s2"] = self.pi_acceleration_mm_s2
        super_settings["deceleration_mm_s2"] = self.pi_deceleration_mm_s2
        try:
            super_settings["joystick_direction_inverted"] = (
                self.pi_joystick_direction_inverted
            )
        except Exception:
            pass
        return super_settings

    @settings.setter
    def settings(self, data: Config):
        assert StageInstrument.settings.fset is not None
        StageInstrument.settings.fset(self, data)
        if "velocity_mm_s" in data:
            self.pi_velocity_mm_s = cast(Any, data["velocity_mm_s"])
        if "acceleration_mm_s2" in data:
            self.pi_acceleration_mm_s2 = cast(Any, data["acceleration_mm_s2"])
        if "deceleration_mm_s2" in data:
            self.pi_deceleration_mm_s2 = cast(Any, data["deceleration_mm_s2"])
        if "joystick_direction_inverted" in data:
            self.pi_joystick_direction_inverted = cast(
                Any, data["joystick_direction_inverted"]
            )
