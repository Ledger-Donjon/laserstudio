from .laser import LaserInstrument
import logging
from typing import Any, cast

# Lazy import, LaserDriver is not publicly supported yet.
try:
    from laser_driver import LaserDriver as LaserDriverClass  # type: ignore[reportMissingImports]
except Exception:
    LaserDriverClass = None

LaserDriver = cast(type | None, LaserDriverClass)


class LaserDriverInstrument(LaserInstrument):
    def __init__(self, config: dict[str, Any]):
        """
        :param config: YAML configuration object
        """
        if LaserDriver is None:
            raise ImportError(
                "Optional dependency 'laser_driver' is required for LaserDriverInstrument."
            )
        super().__init__(config=config)
        device_type = config.get("type")
        logging.getLogger("laserstudio").info(f"Connecting to {device_type}... ")
        self.laser = LaserDriver()
        self.laser.laser_enabled = False
