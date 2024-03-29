from PyQt6.QtCore import QTimer, pyqtSignal, QCoreApplication, Qt
from .list_serials import get_serial_device, DeviceSearchError
import logging
from pystages import Corvus, CNCRouter, Stage, Vector
from .stage_rest import StageRest
from .stage_dummy import StageDummy
from pystages.exceptions import ProtocolError
from typing import Optional, cast
from enum import Enum, auto
from .instrument import Instrument


class MoveFor(object):
    class Type(Enum):
        CAMERA_CENTER = auto()
        LASER = auto()
        PROBE = auto()

    def __init__(self, type: Type, index: int = 0):
        self.type = type
        self.index = index


class StageInstrument(Instrument):
    """Class to regroup stage instrument operations"""

    # Signal emitted when a new position is fetched
    position_changed = pyqtSignal(Vector)

    def __init__(self, config: dict):
        """
        :param config: YAML configuration object
        """
        super().__init__()

        device_type = config.get("type")
        # To refresh stage position in the view, in real-time
        self.refresh_interval = cast(Optional[int], config.get("refresh_interval_ms"))

        self.guardrail = cast(float, config.get("guardrail_um", 20000.0))
        self.guardrail_enabled = True

        dev = config.get("dev")
        if device_type in ["Corvus", "CNC"]:
            if dev is None:
                logging.getLogger("laserstudio").error(
                    f"In configuration file, 'stage.dev' is mandatory for type {device_type}"
                )
                raise

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
            self.stage: Stage = Corvus(dev)
            if self.refresh_interval is None:
                self.refresh_interval = 1000

        elif device_type == "CNC":
            logging.getLogger("laserstudio").info(
                f"Connecting to {device_type} {dev}... "
            )
            self.stage: Stage = CNCRouter(dev)
            if self.refresh_interval is None:
                self.refresh_interval = 200
        elif device_type == "Dummy":
            logging.getLogger("laserstudio").info("Creating a dummy stage... ")
            self.stage: Stage = StageDummy(config=config, stage_instrument=self)
        elif device_type == "REST":
            logging.getLogger("laserstudio").info(f"Connecting to {device_type}...")
            try:
                self.stage: Stage = StageRest(config)
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
                self.refresh_interval, Qt.TimerType.CoarseTimer, self.refresh_stage
            )

        # Unit factor to apply in order to get coordinates in micrometers
        self.unit_factor = config.get("unit_factor", 1.0)
        self.mem_points = [Vector(*i) for i in config.get("mem_points", [])]

        if self.stage is not None:
            self.stage.wait_routine = lambda: QCoreApplication.processEvents()

        # Indicate
        self.move_for = MoveFor(MoveFor.Type.CAMERA_CENTER)

    @property
    def position(self) -> Vector:
        """Get the position of the stage instrument

        :return: Get the position of the stage
        """
        return self.stage.position * self.unit_factor

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

    def refresh_stage(self):
        """Called regularly to get stage position, and emits a pyQtSignal"""
        try:
            self.position_changed.emit(position := self.position)
            logging.getLogger("laserstudio").debug(f"Position refreshed: {position}")
        except ProtocolError as e:
            logging.getLogger("laserstudio").warning(
                f"Warning: Bad response!: {repr(e)}"
            )
        if self.refresh_interval is not None:
            QTimer.singleShot(
                self.refresh_interval, Qt.TimerType.CoarseTimer, self.refresh_stage
            )

    def move_relative(self, displacement: Vector, wait: bool):
        """
        Moves the stage for a specific displacement.

        :param displacement: the displacement to operate as a Vector
        :param wait: True if the stage must wait for move to be completely done

        """
        pos = self.position
        for i, v in enumerate(displacement.data):
            pos[i] += v
        self.move_to(pos, wait=wait)

    def move_to(self, position: Vector, wait: bool):
        """
        Moves associated stage to a specific position, optionally waits for stage to stop moving.

        :param position: destination as a Vector
        :param wait: True if the stage must wait for move to be completely done

        .. note::
            If there is a configuration of z-offsetting for each move, it will be done and
            intermediates moves are blocking (eg, waiting to be done).
        """
        if self.guardrail_enabled:
            displacement = self.position - position
            for i, displacement in enumerate(displacement.data):
                if abs(displacement) > self.guardrail:
                    logging.getLogger("laserstudio").error(
                        f"Do not move!! One axis ({i}) moves further than {self.guardrail}µm: {displacement}µm"
                    )
                    return
        # Move to actual destination
        self.stage.move_to(position / self.unit_factor, wait=wait)
