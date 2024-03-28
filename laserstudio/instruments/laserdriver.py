from laser_driver import LaserDriver
from .laser import LaserInstrument
import logging


class LaserDriverInstrument(LaserInstrument):
    def __init__(self, config: dict):
        """
        :param config: YAML configuration object
        """
        super().__init__(config=config)
        device_type = config.get("type")
        logging.getLogger("laserstudio").info(f"Connecting to {device_type}... ")
        self.laser = LaserDriver()
        self.laser.laser_enabled = False
