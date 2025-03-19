from .stage import StageInstrument
from .list_serials import DeviceSearchError
from .camera import CameraInstrument
from .camera_rest import CameraRESTInstrument
from .camera_usb import CameraUSBInstrument
from .camera_nit import CameraNITInstrument
from .light import LightInstrument
from .hayashilight import HayashiLRInstrument
from .lmscontroller import LMSControllerInstrument
from .laser import LaserInstrument
from .laserdriver import LaserDriverInstrument, LaserDriver  # type: ignore
from .pdm import PDMInstrument
from .probe import ProbeInstrument
from typing import Optional, cast, Any
import sys
import logging


class Instruments:
    """Class to regroup and manage all the instruments."""

    def __init__(self, config: dict):
        """
        :param config: Configuration YAML object
        """
        # Main stage
        self.stage = None
        stage_config = config.get("stage", None)
        if stage_config is not None and stage_config.get("enable", True):
            try:
                self.stage = StageInstrument(stage_config)
            except DeviceSearchError as e:
                logging.getLogger("laserstudio").warning(
                    f"Stage is enabled but device {str(e)} is not found... Skipping."
                )
            except Exception as e:
                logging.getLogger("laserstudio").warning(
                    f"Stage is enabled but device could not be created: {str(e)}... Skipping."
                )
                self.stage = None

        # Main camera
        self.camera = None
        camera_config = config.get("camera", None)
        if camera_config is not None and camera_config.get("enable", True):
            device_type = camera_config.get("type")
            try:
                if device_type == "USB":
                    self.camera: Optional[CameraInstrument] = CameraUSBInstrument(
                        camera_config
                    )
                elif device_type == "REST":
                    self.camera: Optional[CameraInstrument] = CameraRESTInstrument(
                        camera_config
                    )
                elif device_type == "NIT":
                    if sys.platform != "linux" and sys.platform != "win32":
                        raise Exception(
                            "The NIT camera is not supported on other platforms than Linux or Windows."
                        )
                    self.camera: Optional[CameraInstrument] = CameraNITInstrument(
                        camera_config
                    )
            except Exception as e:
                logging.getLogger("laserstudio").warning(
                    f"Camera is enabled but device could not be created: {str(e)}... Skipping."
                )
                self.camera = None

        # Laser modules
        self.lasers: list[LaserInstrument] = []
        lasers_config = cast(list[dict], config.get("lasers", None))
        if lasers_config is not None:
            for laser_config in lasers_config:
                if not laser_config.get("enable", True):
                    continue
                device_type = laser_config.get("type")
                try:
                    if device_type == "PDM":
                        self.lasers.append(PDMInstrument(config=laser_config))
                    elif LaserDriver is not None and device_type == "DonjonLaser":
                        self.lasers.append(LaserDriverInstrument(config=laser_config))
                    else:
                        logging.getLogger("laserstudio").error(
                            f"Unknown laser type {device_type}. Skipping device."
                        )
                        raise
                except Exception as e:
                    logging.getLogger("laserstudio").warning(
                        f"Laser is enabled but device could not be created: {str(e)}... Skipping."
                    )

        # Probes
        self.probes: list[ProbeInstrument] = []
        probes_config = cast(list[dict], config.get("probes", None))
        if probes_config is not None:
            for probe_config in probes_config:
                if not probe_config.get("enable", True):
                    continue
                self.probes.append(ProbeInstrument(config=probe_config))

        # Lighting system
        self.light: Optional[LightInstrument] = None
        light_config = config.get("ligth", None)
        if light_config is not None and light_config.get("enable", True):
            device_type = light_config.get("type")
            try:
                if device_type == "Hayashi":
                    self.light = HayashiLRInstrument(light_config)
                elif device_type == "LMSController":
                    self.light = LMSControllerInstrument(light_config)
                else:
                    logging.getLogger("laserstudio").error(
                        f"Unknown Lighting system type {device_type}. Skipping device."
                    )
                    raise

            except Exception as e:
                logging.getLogger("laserstudio").warning(
                    f"Lighting system is enabled but device could not be created: {str(e)}... Skipping."
                )

    def go_next(self) -> dict[str, Any]:
        results = []
        for laser in self.lasers:
            results.append(laser.go_next())
        return {"lasers": results}
