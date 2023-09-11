from PyQt6.QtCore import QTimer, pyqtSignal, QObject, QCoreApplication
from .list_serials import get_serial_device
import logging
from pystages import Corvus, Stage


class StageInstrument(QObject):
    """Class to regroup stage instrument operations"""

    def __init__(self, config: dict):
        """
        :param config: YAML configuration object
        """
        super().__init__()

        dev = get_serial_device(config.get("dev"))
        device_type = config.get("type")

        if dev is None or device_type is None:
            logging.error(
                "In configuration file, 'dev' and 'type' fields are mandatory for Stages"
            )
            return

        logging.info(f"Connecting to {device_type} {dev}... ")

        if device_type == "Corvus":
            self.stage: Stage = Corvus(dev)
        else:
            logging.error(f"Unknown stage type {device_type}")
            return
