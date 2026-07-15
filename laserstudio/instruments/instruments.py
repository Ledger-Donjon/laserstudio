from typing import Any, Sequence
from .stage import StageInstrument
from .list_serials import DeviceSearchError
from .camera import CameraInstrument
from .camera_rest import CameraRESTInstrument
from .camera_usb import CameraUSBInstrument
from .camera_nit import CameraNITInstrument
from .camera_raptor import CameraRaptorInstrument
from .light import LightInstrument
from .hayashilight import HayashiLRInstrument
from .focus import FocusInstrument
from .instrument import Instrument
from .lmscontroller import LMSControllerInstrument
from .laser import LaserInstrument
from .laser_dummy import LaserDummy
from .laserdriver import LaserDriverInstrument
from .pdm import PDMInstrument
from .probe import ProbeInstrument
from ..utils.yaml_types import Config
import sys
import logging


class Instruments:
    """Class to regroup and manage all the instruments."""

    def __init__(self, config: Config):
        """
        :param config: Configuration YAML object
        """
        # Main stage
        self.stage: StageInstrument | None = None
        stage_config = config.get("stage")
        if type(stage_config) is dict:
            if not stage_config.get("enable", True):
                logging.getLogger("laserstudio").info(
                    "Stage is disabled in configuration file... Skipping."
                )
            else:
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
        self.camera: CameraInstrument | None = None
        camera_config = config.get("camera")
        if type(camera_config) is dict:
            if not camera_config.get("enable", True):
                logging.getLogger("laserstudio").info(
                    "Camera is disabled in configuration file... Skipping."
                )
            else:
                device_type = camera_config.get("type")
                try:
                    if device_type == "USB":
                        self.camera = CameraUSBInstrument(camera_config)
                    elif device_type == "REST":
                        self.camera = CameraRESTInstrument(camera_config)
                    elif device_type == "NIT":
                        if sys.platform != "linux" and sys.platform != "win32":
                            raise Exception(
                                "The NIT camera is not supported on other platforms than Linux or Windows."
                            )
                        self.camera = CameraNITInstrument(camera_config)
                    elif device_type == "Raptor":
                        self.camera = CameraRaptorInstrument(camera_config)
                except Exception as e:
                    logging.getLogger("laserstudio").warning(
                        f"Camera is enabled but device of type {device_type} could not be created: {str(e)}... Skipping."
                    )

        # Laser modules
        self.lasers: list[LaserInstrument] = []
        lasers_config = config.get("lasers")
        if type(lasers_config) is list:
            for i, laser_config in enumerate(lasers_config):
                if not laser_config.get("enable", True):
                    logging.getLogger("laserstudio").info(
                        f"Laser {i + 1} is disabled in configuration file... Skipping."
                    )
                    continue
                device_type = laser_config.get("type")
                try:
                    if device_type == "PDM":
                        self.lasers.append(PDMInstrument(config=laser_config))
                    elif device_type == "DonjonLaser":
                        self.lasers.append(LaserDriverInstrument(config=laser_config))
                    elif device_type == "Dummy":
                        self.lasers.append(LaserDummy(config=laser_config))
                    else:
                        logging.getLogger("laserstudio").error(
                            f"Laser {i + 1} is enabled but has an unknown type {device_type}... Skipping device."
                        )
                except Exception as e:
                    logging.getLogger("laserstudio").warning(
                        f"Laser {i + 1} is enabled but device of type {device_type} could not be created: {str(e)}... Skipping."
                    )

        # Probes
        self.probes: list[ProbeInstrument] = []
        probes_config = config.get("probes")
        if type(probes_config) is list:
            for i, probe_config in enumerate(probes_config):
                if not probe_config.get("enable", True):
                    logging.getLogger("laserstudio").info(
                        f"Probe {i + 1} is disabled in configuration file... Skipping."
                    )
                    continue
                self.probes.append(ProbeInstrument(config=probe_config))

        # Autofocus helper: stores registered position in order to do automatic camera
        # focusing. This can be considered as an abstract instrument.
        self.focus_helper: FocusInstrument | None = None
        if self.camera is not None and self.stage is not None:
            focus_config = config.get("focus", {})
            if type(focus_config) is dict:
                self.focus_helper = FocusInstrument(
                    focus_config, self.camera, self.stage
                )

        # Lighting system
        self.light: LightInstrument | None = None
        light_config = config.get("lighting")
        if type(light_config) is dict:
            if not light_config.get("enable", True):
                logging.getLogger("laserstudio").info(
                    "Lighting system is disabled in configuration file... Skipping."
                )
            else:
                device_type = light_config.get("type")
                try:
                    if device_type == "Hayashi":
                        self.light = HayashiLRInstrument(light_config)
                    elif device_type == "LMSController":
                        self.light = LMSControllerInstrument(light_config)
                    else:
                        logging.getLogger("laserstudio").error(
                            f"Lighting system is enabled but has an unknown type {device_type}... Skipping device."
                        )
                except Exception as e:
                    logging.getLogger("laserstudio").warning(
                        f"Lighting system is enabled but device of type {device_type} could not be created: {str(e)}... Skipping."
                    )

    def go_next(self) -> Config:
        results: list[dict[str, Any]] = []
        for laser in self.lasers:
            results.append(laser.go_next())
        return {"lasers": results}

    @property
    def all_instruments(self) -> Sequence[Instrument]:
        all: list[Instrument] = []
        if self.stage is not None:
            all.append(self.stage)
        if self.camera is not None:
            all.append(self.camera)
        all.extend(self.lasers)
        all.extend(self.probes)
        if self.light is not None:
            all.append(self.light)
        return all

    def get_instrument_with_label(self, label: str) -> Instrument | None:
        for instrument in self.all_instruments:
            if instrument.label == label:
                return instrument
        return None

    def set_log_level(self, level: int) -> None:
        for instrument in self.all_instruments:
            instrument.set_log_level(level)
        if self.focus_helper is not None:
            self.focus_helper.set_log_level(level)
