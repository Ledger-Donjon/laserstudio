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
            except Exception as e:
                logging.getLogger("laserstudio").warning(
                    f"Stage is enabled but device could not be created: {str(e)}... Skipping."
                )
                self.stage = None

        # Main camera
        self.camera = None
        camera_config = config.get("camera", None)
        if camera_config is not None and camera_config.get("enable", False):
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
            except Exception as e:
                logging.getLogger("laserstudio").warning(
                    f"Camera is enabled but device could not be created: {str(e)}... Skipping."
                )
                self.camera = None

    def go_next(self):
        pass
