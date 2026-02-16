from __future__ import annotations
import logging
from typing import cast, Any
from enum import Enum, auto
from PyQt6.QtCore import QTimer, pyqtSignal, Qt, QMutex
from pystages.exceptions import ProtocolError
from pystages import (
    Corvus,
    CNCRouter,
    Stage,
    Vector as PystagesVector,
    Autofocus,
    Tic,
    TicDirection,
    SMC100,
    PI,
)
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
    "Autofocus",
    "Tic",
    "TicDirection",
    "StageRest",
    "StageDummy",
    "get_serial_device",
    "DeviceSearchError",
    "Instrument",
    "MoveFor",
]


class Vector(PystagesVector):
    """Vector class for stage instrument.

    Provides typed accessors over the base pystages.Vector.
    """

    data: list[float]

    @property
    def x(self) -> float:
        return self.data[0]

    @x.setter
    def x(self, value: float):
        self.data[0] = value

    @property
    def y(self) -> float:
        return self.data[1]

    @y.setter
    def y(self, value: float):
        self.data[1] = value

    @property
    def z(self) -> float:
        return self.data[2]

    @z.setter
    def z(self, value: float):
        self.data[2] = value

    @property
    def w(self) -> float:
        return self.data[3]

    @w.setter
    def w(self, value: float):
        self.data[3] = value

    @property
    def xy(self) -> Vector:
        return Vector(self.x, self.y)

    @xy.setter
    def xy(self, value: Vector):
        self.x = value.x
        self.y = value.y

    def __getitem__(self, key: int) -> float:
        return self.data[key]

    def __setitem__(self, key: int, value: float):
        self.data[key] = value


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

    def __init__(self, config: dict[str, Any]):
        """
        :param config: YAML configuration object
        """
        super().__init__(config)
        self.mutex = QMutex()

        device_type = config.get("type")
        # To refresh stage position in the view, in real-time
        self.refresh_interval = cast(int | None, config.get("refresh_interval_ms"))

        self.guardrail = cast(float, config.get("guardrail_um", 20000.0))
        self.guardrail_enabled = True

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
            self.stage = StageDummy(config=config, stage_instrument=self)
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

        # Indicate
        self.move_for = MoveFor(MoveFor.Type.CAMERA_CENTER)

    @property
    def position(self) -> Vector:
        """Get the position of the stage instrument

        :return: Get the position of the stage
        """
        self.mutex.lock()
        position = Vector(*[float(v) for v in self.stage.position.data])
        self.mutex.unlock()

        # Apply shearing transformation
        x = position.x
        y = position.y

        position.x = x - self.shear[0] * y
        position.y = y - self.shear[1] * x

        factors = self.unit_factors
        if isinstance(factors, float) or isinstance(factors, int):
            factors = [float(factors)] * len(position)
        for i in range(len(position)):
            position[i] = position[i] * factors[i] + self.offset_origin[i]

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
        try:
            self.position_changed.emit(position := self.position)
            logging.getLogger("laserstudio").debug(f"Position refreshed: {position}")
        except ProtocolError as e:
            logging.getLogger("laserstudio").warning(
                f"Warning: Bad response!: {repr(e)}"
            )
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
            for i, displacement_i in enumerate(displacement.data):
                if abs(displacement_i) > self.guardrail:
                    logging.getLogger("laserstudio").error(
                        f"Do not move!! One axis ({i}) moves further than {self.guardrail}\xa0µm: {displacement}\xa0µm"
                    )
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

        self.mutex.lock()
        if backlash and len(self.backlashes) == len(position):
            backlashes = Vector(*self.backlashes)
            # Apply unit factors
            for i in range(len(backlashes)):
                backlashes[i] = backlashes[i] / factors[i]
            self.stage.move_to(result - backlashes, wait=True)
        self.stage.move_to(result, wait=wait)
        if isinstance(self.stage, Corvus):
            self.stage.enable_joystick()
        self.mutex.unlock()
        _ = self.position

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
