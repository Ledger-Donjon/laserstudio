from .stage import StageInstrument
from .list_serials import DeviceSearchError
from .camera import CameraInstrument
from .camera_rest import CameraRESTInstrument
from .camera_usb import CameraUSBInstrument
from typing import Optional
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
        if stage_config is not None and stage_config.get("enable", False):
            try:
                self.stage = StageInstrument(stage_config)
            except DeviceSearchError as e:
                logging.getLogger("laserstudio").warning(
                    f"Stage is enabled but device {str(e)} is not found... Skipping."
                )

        # Main camera
        self.camera = None
        camera_config = config.get("camera", None)
        if camera_config is not None and camera_config.get("enable", False):
            if camera_config.get("type") == "USB":
                self.camera: Optional[CameraInstrument] = CameraUSBInstrument(
                    camera_config
                )

            if camera_config.get("type") == "REST":
                self.camera: Optional[CameraInstrument] = CameraRESTInstrument(
                    camera_config
                )

    def go_next(self):
        pass
