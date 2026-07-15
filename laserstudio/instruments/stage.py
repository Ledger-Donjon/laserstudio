from __future__ import annotations
import logging
import math
from typing import cast, Any, SupportsIndex, overload
from enum import Enum, auto
from PyQt6.QtCore import QTimer, pyqtSignal, Qt, QMutex
from pystages.exceptions import ProtocolError
from pystages import (
    Corvus,
    CNCRouter,
    CNCError,
    Stage,
    Vector as PystagesVector,
    Autofocus,
    Tic,
    TicDirection,
    SMC100,
    PI,
)
from ..utils.grbl_alarms import format_grbl_alarm_message
from .stage_rest import StageRest
from .stage_dummy import StageDummy
from .list_serials import get_serial_device, DeviceSearchError
from .instrument import Instrument
from ..utils.yaml_types import Config

__all__ = [
    "StageInstrument",
    "MoveFor",
    "Autofocus",
    "Tic",
    "TicDirection",
    "Vector",
    "ProtocolError",
    "Corvus",
    "CNCRouter",
    "SMC100",
    "PI",
    "Stage",
    "StageRest",
    "StageDummy",
    "get_serial_device",
    "DeviceSearchError",
    "Instrument",
]


class Vector(PystagesVector):
    """Vector class for stage instrument.

    Provides typed accessors over the base pystages.Vector.
    """

    data: list[float]

    @property
    def x(self) -> float:
        if len(self.data) < 1:
            return float("nan")
        return self.data[0]

    @x.setter
    def x(self, value: float):
        self.data[0] = value

    @property
    def y(self) -> float:
        if len(self.data) < 2:
            return float("nan")
        return self.data[1]

    @y.setter
    def y(self, value: float):
        self.data[1] = value

    @property
    def z(self) -> float:
        if len(self.data) < 3:
            return float("nan")
        return self.data[2]

    @z.setter
    def z(self, value: float):
        self.data[2] = value

    @property
    def w(self) -> float:
        if len(self.data) < 4:
            return float("nan")
        return self.data[3]

    @w.setter
    def w(self, value: float):
        self.data[3] = value

    @property
    def xy(self) -> Vector:
        return Vector(self.x, self.y)

    @xy.setter
    def xy(self, value: PystagesVector):
        if not isinstance(value, Vector):
            raise ValueError(f"Invalid value type: {type(value)}")
        self.x = value.x
        self.y = value.y

    @overload
    def __getitem__(self, key: SupportsIndex) -> float: ...

    @overload
    def __getitem__(self, key: slice) -> list[float]: ...

    def __getitem__(self, key: SupportsIndex | slice) -> float | list[float]:
        if isinstance(key, slice):
            return self.data[key]
        else:
            return self.data[key]

    @overload
    def __setitem__(self, key: SupportsIndex, value: float) -> None: ...
    @overload
    def __setitem__(self, key: slice, value: list[float]) -> None: ...

    def __setitem__(self, key: SupportsIndex | slice, value: float | list[float]):
        if isinstance(key, slice) and isinstance(value, list):
            self.data[key] = value
        elif isinstance(key, SupportsIndex) and isinstance(value, float):
            self.data[key] = value
        else:
            raise ValueError(f"Inconsistent types in {key=} and {value=}")


class MoveFor(object):
    """
    A MoveFor object, used to define the object for focus
    when performing a move.
    """

    class Type(Enum):
        """
        The type of object to focus on.
        """

        CAMERA_CENTER = auto()
        LASER = auto()
        PROBE = auto()

    def __init__(self, type: Type, index: int = 0):
        """
        Initialize the MoveFor object.

        :param type: The type of object to focus on.
        :param index: The index of the object to focus on, in the case of Laser or Probe.
        """
        self.type = type
        self.index = index


class StageInstrument(Instrument):
    """Class to regroup stage instrument operations"""

    # Signal emitted when a new position is fetched
    position_changed = pyqtSignal(Vector)
    grbl_alarm = pyqtSignal(str)
    # Signal emitted when the "Max move distance" guardrail (value or enabled
    # state) changes.
    guardrail_changed = pyqtSignal()
    # Signal emitted when the "Stage area limit" (bounds or enabled state) change
    soft_limits_changed = pyqtSignal()
    # Signal emitted when a move is rejected because it falls outside the limits
    soft_limit_violation = pyqtSignal(str)

    def __init__(self, config: dict[str, Any]):
        """
        :param config: YAML configuration object
        """
        super().__init__(config)
        self.mutex = QMutex()
        self._last_reported_alarm: tuple[int | None, str] | None = None

        device_type = config.get("type")
        # To refresh stage position in the view, in real-time
        self.refresh_interval = cast(int | None, config.get("refresh_interval_ms"))

        # "Max move distance" guardrail: block any single move whose amplitude
        # exceeds this distance (per axis), in stage µm. Independently toggleable.
        self._guardrail = float(cast(float, config.get("guardrail_um", 20000.0)))
        self._guardrail_enabled = bool(config.get("guardrail_enabled", True))

        self.backlashes = cast(list[float], config.get("backlashes_um"))

        self.shear = cast(list[float], config.get("shear", [0.0, 0.0]))

        dev = config.get("dev")
        if dev == "":
            dev = None
        if device_type in ["Corvus", "CNC", "SMC100"] and dev is None:
            logging.getLogger("laserstudio").error(
                f"In configuration file, 'stage.dev' is mandatory for type {device_type}"
            )
            raise

        if device_type in ["Corvus", "CNC", "SMC100", "PI"] and dev is not None:
            try:
                dev = get_serial_device(dev)
            except DeviceSearchError as e:
                logging.getLogger("laserstudio").error(
                    f"Stage is enabled but device is not found: {str(e)}...  Skipping."
                )
                raise

        if device_type == "Corvus":
            logging.getLogger("laserstudio").info(
                f"Connecting to {device_type} {dev}... "
            )
            self.stage = Corvus(dev)
            if self.refresh_interval is None:
                self.refresh_interval = 1000

        elif device_type == "CNC":
            logging.getLogger("laserstudio").info(
                f"Connecting to {device_type} {dev}... "
            )
            self.stage = CNCRouter(dev)
            if self.refresh_interval is None:
                self.refresh_interval = 200


        elif device_type == "PI":
            logging.getLogger("laserstudio").info(
                "Creating a PI/Mercury stage... "
                + f"Connecting to {device_type} {dev}... "
            )
            adresses = config.get("adresses", [1, 2, 3])
            logging.getLogger("laserstudio").info(f"Connecting to {adresses}... ")
            self.stage = PI(dev=dev, addresses=adresses)
        elif device_type == "SMC100":
            logging.getLogger("laserstudio").info(
                "Creating a SMC100 stage... " + f"Connecting to {device_type} {dev}... "
            )
            adresses = config.get("adresses", [1, 2])
            logging.getLogger("laserstudio").info(f"Connecting to {adresses}... ")
            self.stage = SMC100(dev=dev, addresses=adresses)
        elif device_type == "Dummy":
            logging.getLogger("laserstudio").info("Creating a dummy stage... ")
            self.stage = StageDummy(config=config)
        elif device_type == "REST":
            logging.getLogger("laserstudio").info(f"Connecting to {device_type}...")
            try:
                self.stage = StageRest(config)
            except Exception as e:
                logging.getLogger("laserstudio").error(
                    f"Connection to {device_type} stage failed: {str(e)}. Skipping device."
                )
                raise
            if self.refresh_interval is None:
                self.refresh_interval = 2000
        else:
            logging.getLogger("laserstudio").error(
                f"Unknown stage type {device_type}. Skipping device."
            )
            raise

        if self.refresh_interval is not None:
            QTimer.singleShot(
                self.refresh_interval,
                Qt.TimerType.CoarseTimer,
                self.__autorefresh_stage,
            )

        # Unit factor to apply in order to get coordinates in micrometers
        factors = cast(
            list[float], config.get("unit_factor", config.get("unit_factors", [1.0]))
        )
        position = self.stage.position
        if isinstance(factors, int) or isinstance(factors, float):
            logging.getLogger("laserstudio").warning(
                f"Unit factor {factors} is a single value, it will be repeated for all axes."
            )
            factors = [float(factors)] * len(position)

        if len(factors) != len(position):
            logging.getLogger("laserstudio").warning(
                f"Unit factors {factors} has an inconsistent length from the number of axes ({len(position)}). Please check your configuration file"
            )
            if len(factors) == 0:
                logging.getLogger("laserstudio").warning(
                    "No unit factors provided. 1.0 will be repeated for all axes."
                )
                factors = [1.0] * len(position)

            if len(factors) < len(position):
                last_value = factors[-1]
                logging.getLogger("laserstudio").warning(
                    f"Last value ({last_value}) will be repeated to the number of axes."
                )
                factors = factors + [last_value] * (len(position) - len(factors))

            if len(factors) > len(position):
                # Truncate array if there is too much values for the number of axes
                logging.getLogger("laserstudio").warning(
                    "Values will be truncated to the number of axes"
                )
                factors = factors[: len(position)]

        self.unit_factors: list[float] = factors

        # Offset origin
        self.offset_origin: list[float] = cast(
            list[float], config.get("offset_origin", [0.0] * self.num_axis)
        )
        assert (
            type(self.offset_origin) is list
            and len(self.offset_origin) == self.num_axis
        ), (
            f"Offset origin {self.offset_origin} is not a list of {self.num_axis} numbers. "
            "Please check your configuration file"
        )

        self.mem_points = [Vector(*i) for i in config.get("mem_points", [])]

        # Software limits (LaserStudio-side), expressed in stage µm coordinates.
        # When enabled, a move whose target falls outside [min, max] on any
        # constrained axis is rejected. These are independent from any firmware
        # soft limits (e.g. GRBL $20).
        self._soft_limits_enabled: bool = bool(
            config.get("soft_limits_enabled", False)
        )
        self._soft_limits_min: list[float] | None = None
        self._soft_limits_max: list[float] | None = None
        soft_min = config.get("soft_limits_min")
        soft_max = config.get("soft_limits_max")
        if soft_min is not None and soft_max is not None:
            self._set_soft_limits_raw(
                cast(list[float], soft_min), cast(list[float], soft_max)
            )

        # Indicate
        self.move_for = MoveFor(MoveFor.Type.CAMERA_CENTER)

    def set_log_level(self, level: int) -> None:
        if hasattr(self.stage, "logger"):
            self.stage.logger.setLevel(level)

    def _handle_cnc_error(self, error: CNCError, *, notify: bool = False) -> None:
        message = format_grbl_alarm_message(error)
        alarm_key = (error.alarm_code, error.args[0] if error.args else "")
        if alarm_key != self._last_reported_alarm:
            self._last_reported_alarm = alarm_key
            logging.getLogger("laserstudio").warning(message)
            if notify:
                self.grbl_alarm.emit(message)

    def clear_grbl_alarm_state(self) -> None:
        """Clear the GRBL alarm state so position polling can resume after unlock."""
        self._last_reported_alarm = None

    def _pad_axes(self, values: list[float]) -> list[float]:
        """Pad/truncate a list of values to match the number of axes."""
        values = list(values[: self.num_axis])
        if len(values) < self.num_axis:
            values += [0.0] * (self.num_axis - len(values))
        return values

    def _set_soft_limits_raw(
        self, minimum: list[float], maximum: list[float]
    ) -> None:
        """Set the soft limits without emitting any signal (used at init)."""
        minimum = self._pad_axes([float(v) for v in minimum])
        maximum = self._pad_axes([float(v) for v in maximum])
        # Make sure min <= max on each axis.
        for i in range(self.num_axis):
            if minimum[i] > maximum[i]:
                minimum[i], maximum[i] = maximum[i], minimum[i]
        self._soft_limits_min = minimum
        self._soft_limits_max = maximum

    @property
    def guardrail(self) -> float:
        """Maximum allowed amplitude of a single move (per axis), in stage µm.

        This is the "Max move distance" guardrail: any move longer than this on
        any axis is blocked when :attr:`guardrail_enabled` is True.
        """
        return self._guardrail

    @guardrail.setter
    def guardrail(self, value: float) -> None:
        value = max(0.0, float(value))
        if value == self._guardrail:
            return
        self._guardrail = value
        self.guardrail_changed.emit()

    @property
    def guardrail_enabled(self) -> bool:
        """Whether the "Max move distance" guardrail is enforced on moves."""
        return self._guardrail_enabled

    @guardrail_enabled.setter
    def guardrail_enabled(self, value: bool) -> None:
        value = bool(value)
        if value == self._guardrail_enabled:
            return
        self._guardrail_enabled = value
        self.guardrail_changed.emit()

    @property
    def soft_limits_enabled(self) -> bool:
        """Whether the LaserStudio software limits are enforced on moves."""
        return self._soft_limits_enabled

    @soft_limits_enabled.setter
    def soft_limits_enabled(self, value: bool) -> None:
        value = bool(value)
        if value == self._soft_limits_enabled:
            return
        self._soft_limits_enabled = value
        self.soft_limits_changed.emit()

    @property
    def soft_limits_min(self) -> list[float] | None:
        """Lower bounds of the software limits per axis (stage µm), or None."""
        return None if self._soft_limits_min is None else list(self._soft_limits_min)

    @property
    def soft_limits_max(self) -> list[float] | None:
        """Upper bounds of the software limits per axis (stage µm), or None."""
        return None if self._soft_limits_max is None else list(self._soft_limits_max)

    @property
    def has_soft_limits(self) -> bool:
        """True if a software limit box has been defined."""
        return self._soft_limits_min is not None and self._soft_limits_max is not None

    def set_soft_limits(
        self, minimum: list[float], maximum: list[float]
    ) -> None:
        """Define the software limit box (stage µm coordinates) and notify."""
        self._set_soft_limits_raw(minimum, maximum)
        self.soft_limits_changed.emit()

    def _ensure_soft_limits(self) -> None:
        """Make sure a limit box exists, defaulting to the current position."""
        if not self.has_soft_limits:
            base = self._pad_axes([float(v) for v in self.position.data])
            self._soft_limits_min = list(base)
            self._soft_limits_max = list(base)

    def _set_axis_no_emit(self, axis: int, low: float, high: float) -> None:
        self._ensure_soft_limits()
        assert self._soft_limits_min is not None and self._soft_limits_max is not None
        if axis < 0 or axis >= self.num_axis:
            return
        if low > high:
            low, high = high, low
        self._soft_limits_min[axis] = float(low)
        self._soft_limits_max[axis] = float(high)

    def set_soft_limits_axis(self, axis: int, low: float, high: float) -> None:
        """Update the software limits for a single axis."""
        self._set_axis_no_emit(axis, low, high)
        self.soft_limits_changed.emit()

    def set_soft_limits_xy(
        self, xmin: float, ymin: float, xmax: float, ymax: float
    ) -> None:
        """Update the X and Y software limits in one shot (single notification)."""
        self._set_axis_no_emit(0, xmin, xmax)
        self._set_axis_no_emit(1, ymin, ymax)
        self.soft_limits_changed.emit()

    def _is_within_soft_limits(self, position: Vector) -> tuple[bool, int | None]:
        """Check a target position against the soft limits.

        :return: (ok, axis) where axis is the first violated axis index if any.
        """
        if (
            not self._soft_limits_enabled
            or self._soft_limits_min is None
            or self._soft_limits_max is None
        ):
            return True, None
        tol = 1e-6
        for i in range(min(len(position), self.num_axis)):
            if (
                position[i] < self._soft_limits_min[i] - tol
                or position[i] > self._soft_limits_max[i] + tol
            ):
                return False, i
        return True, None

    def _read_raw_position(self) -> Vector:
        """Read the device position. The stage mutex must already be locked."""
        return Vector(*[float(v) for v in self.stage.position.data])

    def _apply_position_transforms(self, position: Vector) -> Vector:
        x = position.x
        y = position.y

        position.x = x - self.shear[0] * y
        position.y = y - self.shear[1] * x

        factors = self.unit_factors
        if isinstance(factors, float) or isinstance(factors, int):
            factors = [float(factors)] * len(position)
        for i in range(len(position)):
            position[i] = position[i] * factors[i] + self.offset_origin[i]
        return position

    @property
    def position(self) -> Vector:
        """Get the position of the stage instrument

        :return: Get the position of the stage
        """
        self.mutex.lock()
        try:
            position = self._apply_position_transforms(self._read_raw_position())
        finally:
            self.mutex.unlock()

        self.position_changed.emit(position)
        return position

    @position.setter
    def position(self, value: Vector):
        """
        Moves associated stage to a specific position, without waiting for move to be completely done.

        :param value: destination as a Vector

        .. note::
            If there is a configuration of z-offsetting for each move, it will be done and
            intermediates moves are blocking (eg, waiting to be done).
        """
        self.move_to(value, wait=False)

    def __autorefresh_stage(self):
        """Called regularly to get stage position, and emits a pyQtSignal
        This method is not public, it is called by a QTimer to refresh the stage position regularly."""
        if self._last_reported_alarm is not None:
            if self.refresh_interval is not None:
                QTimer.singleShot(
                    self.refresh_interval,
                    Qt.TimerType.CoarseTimer,
                    self.__autorefresh_stage,
                )
            return

        if not self.mutex.tryLock():
            if self.refresh_interval is not None:
                QTimer.singleShot(
                    self.refresh_interval,
                    Qt.TimerType.CoarseTimer,
                    self.__autorefresh_stage,
                )
            return

        try:
            position = self._apply_position_transforms(self._read_raw_position())
            self._last_reported_alarm = None
            logging.getLogger("laserstudio").debug(f"Position refreshed: {position}")
        except CNCError as e:
            self._handle_cnc_error(e)
        except ProtocolError as e:
            logging.getLogger("laserstudio").warning(
                f"Warning: Bad response!: {repr(e)}"
            )
        except Exception as e:
            logging.getLogger("laserstudio").error(
                f"Error: {repr(e)}", exc_info=True
            )
        else:
            self.position_changed.emit(position)
        finally:
            self.mutex.unlock()

        if self.refresh_interval is not None:
            QTimer.singleShot(
                self.refresh_interval,
                Qt.TimerType.CoarseTimer,
                self.__autorefresh_stage,
            )

    def move_relative(self, displacement: Vector, wait: bool, backlash: bool = False):
        """
        Moves the stage for a specific displacement.

        :param displacement: the displacement to operate as a Vector
        :param wait: True if the stage must wait for move to be completely done

        """
        pos = self.position
        for i, v in enumerate(displacement.data):
            # Prevent crashes if the stage has less axis than the displacement
            if i >= len(pos):
                break
            pos[i] += v
        self.move_to(pos, wait=wait, backlash=backlash)

    def move_to(self, position: Vector, wait: bool, backlash: bool = False):
        """
        Moves associated stage to a specific position, optionally waits for stage to stop moving.

        :param position: destination as a Vector
        :param wait: True if the stage must wait for move to be completely done

        .. note::
            If there is a configuration of z-offsetting for each move, it will be done and
            intermediates moves are blocking (eg, waiting to be done).
        """
        # Make sure about the dimension of the position vector
        if len(position) > self.num_axis:
            logging.getLogger("laserstudio").warning(
                f"Position dimension {len(position)} is greater than the number of axes {self.num_axis}. Extra axes will be ignored."
            )
            position = Vector(*position.data[: self.num_axis])
        elif len(position) < self.num_axis:
            logging.getLogger("laserstudio").warning(
                f"Position dimension {len(position)} is less than the number of axes {self.num_axis}. Missing axes will be set to their current position."
            )
            current_position = self.position
            extra_positions = [
                current_position[i] for i in range(len(position), self.num_axis)
            ]
            position = Vector(*(position.data + extra_positions))

        logging.getLogger("laserstudio").debug(f"Moving to {position}...")
        if self.guardrail_enabled:
            displacement = self.position - position
            # "Max move distance" guardrail: the move is blocked if its Euclidean
            # amplitude exceeds the guardrail radius (represented as a circle in
            # the viewer).
            distance = math.sqrt(sum(d * d for d in displacement.data))
            if distance > self.guardrail:
                logging.getLogger("laserstudio").error(
                    f"Do not move!! Move distance {distance:.1f}\xa0µm exceeds the "
                    f"max move distance of {self.guardrail}\xa0µm: {displacement}\xa0µm"
                )
                return

        within_limits, violated_axis = self._is_within_soft_limits(position)
        if not within_limits and violated_axis is not None:
            axis_name = "XYZ"[violated_axis] if violated_axis < 3 else str(violated_axis)
            message = (
                f"Move blocked by software limits: axis {axis_name} target "
                f"{position[violated_axis]:.1f}\xa0µm is outside the allowed area."
            )
            logging.getLogger("laserstudio").warning(message)
            self.soft_limit_violation.emit(message)
            return

        result = Vector(dim=len(position))

        # Move to actual destination
        factors = self.unit_factors
        assert type(factors) is list and len(factors) == len(position)
        logging.getLogger("laserstudio").debug(
            f"Offset origin: {self.offset_origin}..."
        )
        logging.getLogger("laserstudio").debug(f"Unit factors: {factors}...")

        for i in range(len(position)):
            result[i] = (position[i] - self.offset_origin[i]) / factors[i]
        logging.getLogger("laserstudio").debug(
            f"Position after unit factors and offset origin: {result}..."
        )

        # Apply shearing transformation
        x = result[0]
        y = result[1]

        result[0] = x + self.shear[0] * y
        result[1] = y + self.shear[1] * x
        logging.getLogger("laserstudio").debug(f"Shearing transformation: {result}...")

        move_ok = False
        move_error: CNCError | None = None
        self.mutex.lock()
        try:
            if backlash and len(self.backlashes) == len(position):
                backlashes = Vector(*self.backlashes)
                # Apply unit factors
                for i in range(len(backlashes)):
                    backlashes[i] = backlashes[i] / factors[i]
                self.stage.move_to(result - backlashes, wait=True)
            self.stage.move_to(result, wait=wait)
            if isinstance(self.stage, Corvus):
                self.stage.enable_joystick()
            self._last_reported_alarm = None
            move_ok = True
        except CNCError as e:
            move_error = e
        finally:
            self.mutex.unlock()

        if move_error is not None:
            self._handle_cnc_error(move_error, notify=True)
        elif move_ok:
            try:
                _ = self.position
            except CNCError as e:
                self._handle_cnc_error(e)

    @property
    def num_axis(self) -> int:
        """Get the number of axis of the stage instrument

        :return: Get the number of axis of the stage
        """
        return self.stage.num_axis

    def set_device_origin(self):
        """
        Set the device origin, which is different from the offset correction
        here the device will get the current position as the origin,
        this will be then permanent accross all projects.
        """
        if isinstance(self.stage, Corvus):
            self.stage.set_origin()
        elif isinstance(self.stage, CNCRouter):
            self.stage.set_origin()
        elif isinstance(self.stage, PI):
            self.stage.set_origin()
        else:
            logging.getLogger("laserstudio").error(
                f"Stage of type {type(self.stage)} does not support setting device's origin. Skipping operation."
            )

    @property
    def settings(self) -> Config:
        """
        Return a dict of settings for the stage.
        """
        super_settings = super().settings
        super_settings["offset_origin"] = self.offset_origin
        # "Max move distance" guardrail
        super_settings["guardrail_enabled"] = self._guardrail_enabled
        super_settings["guardrail_um"] = self._guardrail
        # "Stage area limit" guardrail
        super_settings["soft_limits_enabled"] = self._soft_limits_enabled
        if self._soft_limits_min is not None and self._soft_limits_max is not None:
            super_settings["soft_limits_min"] = list(self._soft_limits_min)
            super_settings["soft_limits_max"] = list(self._soft_limits_max)
        logging.getLogger("laserstudio").debug(f"Stage settings: {super_settings}")
        return super_settings

    @settings.setter
    def settings(self, data: Config):
        """
        Set the settings of the stage.
        """
        Instrument.settings.__set__(self, data)
        if "offset_origin" in data:
            assert (
                type(data["offset_origin"]) is list
                and len(data["offset_origin"]) == self.num_axis
            ), (
                f"Offset origin {data['offset_origin']} is not a list of {self.num_axis} numbers. "
                "Please check your settings file"
            )
            self.offset_origin = cast(list[float], data["offset_origin"])
        if "guardrail_um" in data and isinstance(data["guardrail_um"], (int, float)):
            self._guardrail = max(0.0, float(data["guardrail_um"]))
        if "guardrail_enabled" in data:
            self._guardrail_enabled = bool(data["guardrail_enabled"])
        self.guardrail_changed.emit()
        soft_min = data.get("soft_limits_min")
        soft_max = data.get("soft_limits_max")
        if soft_min is not None and soft_max is not None:
            self._set_soft_limits_raw(
                cast(list[float], soft_min), cast(list[float], soft_max)
            )
        if "soft_limits_enabled" in data:
            self._soft_limits_enabled = bool(data["soft_limits_enabled"])
        self.soft_limits_changed.emit()
