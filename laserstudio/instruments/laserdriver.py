# Lazy import, LaserDriver is not pubicly supported yet.
try:
    from laser_driver import LaserDriver  # type: ignore
except Exception:
    LaserDriver = None

from .laser import LaserInstrument
import logging
from typing import Any


class LaserDriverInstrument(LaserInstrument):
    def __init__(self, config: dict[str, Any]):
        """
        :param config: YAML configuration object
        """
        assert LaserDriver is not None
        super().__init__(config=config)
        device_type = config.get("type")
        logging.getLogger("laserstudio").info(f"Connecting to {device_type}... ")
        self.laser = LaserDriver()  # type: ignore
        self.laser.laser_enabled = False  # type: ignore
