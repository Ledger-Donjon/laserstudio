from .camera import CameraInstrument
from .rest_instrument import RestInstrument
from typing import Optional, Literal, cast
import io
from PIL import Image


class CameraRESTInstrument(RestInstrument, CameraInstrument):
    """Class to implement REST cameras"""

    def __init__(self, config: dict):
        """
        :param config: YAML configuration object
        """
        RestInstrument.__init__(self, config)
        CameraInstrument.__init__(self, config)
        self.api_command = cast(str, config.get("api_command", "images/camera"))

    def get_last_image(self) -> tuple[int, int, Literal["L", "I;16", "RGB"], Optional[bytes]]:
        try:
            response = self.get()
        except Exception:
            return 0, 0, "L", None
        im = Image.open(io.BytesIO(response.content))
        im_rgb = im.convert("RGB")
        return *im_rgb.size, "RGB", im.tobytes()
