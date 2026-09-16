import logging
from typing import Any, cast

from pystages import PI

from ..utils.yaml_types import Config
from .stage import StageInstrument


class PIStageInstrument(StageInstrument):
    """Class to regroup PI stage instrument operations"""

    # The base class picks the device from the configured type; declaring it
    # here just narrows it for this subclass (a property would shadow the
    # attribute the base constructor assigns).
    stage: PI

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
            return list(self.stage.joystick_enabled)
        finally:
            self.mutex.unlock()

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

    def set_pi_joystick_axis(self, axis: int, enabled: bool) -> None:
        """Enable or disable the analog joystick on a single PI axis."""
        states = self.pi_joystick_enabled
        states[axis] = enabled
        self.pi_joystick_enabled = states

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
