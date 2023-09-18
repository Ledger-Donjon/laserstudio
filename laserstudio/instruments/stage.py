from PyQt6.QtCore import QTimer, pyqtSignal, QObject, QCoreApplication
from .list_serials import get_serial_device
import logging
from pystages import Corvus, Stage, Vector
from .stage_rest import StageRest
from pystages.exceptions import ProtocolError
from typing import Optional


class StageInstrument(QObject):
    """Class to regroup stage instrument operations"""

    # Signal emitted when a new position is fetched
    position_changed = pyqtSignal(Vector, name="positionChanged")

    def __init__(self, config: dict):
        """
        :param config: YAML configuration object
        """
        super().__init__()

        device_type = config.get("type")
        # To refresh stage position in the view, in real-time
        self._timer = QTimer()
        self._timer.timeout.connect(self.refresh_stage)

        dev = None
        if device_type in ["Corvus"]:
            dev = get_serial_device(config.get("dev"))
            if dev is None or device_type is None:
                logging.getLogger("laserstudio").error(
                    "In configuration file, 'dev' and 'type' fields are mandatory for Stages"
                )
                return

        if device_type == "Corvus":
            logging.getLogger("laserstudio").info(
                f"Connecting to {device_type} {dev}... "
            )
            self.stage: Stage = Corvus(dev)
            self._timer.start(1000)
        elif device_type == "REST":
            logging.getLogger("laserstudio").info(f"Connecting to {device_type}... ")
            self.stage: Stage = StageRest(config)
            self._timer.start(2000)
        else:
            logging.getLogger("laserstudio").error(f"Unknown stage type {device_type}")
            return

        # Unit factor to apply in order to get coordinates in micrometers
        self.unit_factors = config.get("unit_factors", [1.0] * self.stage.num_axis)

    @property
    def position(self) -> Vector:
        """Get the position of the stage instrument

        :return: Get the position of the stage
        """
        return self.stage.position

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

    @property
    def auto_refresh_interval(self) -> Optional[int]:
        """The poll interval of the timer dedicated to get the position regularly, in milliseconds"""
        return self._timer.interval() if self._timer.isActive() else None

    @auto_refresh_interval.setter
    def auto_refresh_interval(self, value: Optional[int]):
        if value is None:
            self._timer.stop()
        else:
            self._timer.start(value)

    def refresh_stage(self):
        """Called regularly to get stage position, and emits a pyQtSignal"""
        try:
            self.position_changed.emit(position := self.position)
            logging.getLogger("laserstudio").debug(f"Position refreshed: {position}")
        except ProtocolError as e:
            logging.getLogger("laserstudio").warning(
                f"Warning: Bad response!: {repr(e)}"
            )

    def move_to(self, position: Vector, wait: bool):
        """
        Moves associated stage to a specific position, optionally waits for stage to stop moving.

        :param position: destination as a Vector
        :param wait: True if the stage must wait for move to be completely done

        .. note::
            If there is a configuration of z-offsetting for each move, it will be done and
            intermediates moves are blocking (eg, waiting to be done).
        """
        # Move to actual destination
        self.stage.move_to(position, wait=wait)
