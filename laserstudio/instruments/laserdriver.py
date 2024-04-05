# Lazy import, LaserDriver is not supported yet.
try:
    from laser_driver import LaserDriver
except Exception:
    LaserDriver = None

from .laser import LaserInstrument
import logging


class LaserDriverInstrument(LaserInstrument):
    def __init__(self, config: dict):
        """
        :param config: YAML configuration object
        """
        assert LaserDriver is not None
        super().__init__(config=config)
        device_type = config.get("type")
        logging.getLogger("laserstudio").info(f"Connecting to {device_type}... ")
        self.laser = LaserDriver()
        self.laser.laser_enabled = False
