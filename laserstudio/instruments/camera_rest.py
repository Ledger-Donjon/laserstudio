import io
from typing import Literal, cast
from PIL import Image
from .camera import CameraInstrument
from .rest_instrument import RestInstrument
from ..utils.yaml_types import Config


class CameraRESTInstrument(RestInstrument, CameraInstrument):
    """Class to implement REST cameras"""

    def __init__(self, config: Config):
        """
        :param config: YAML configuration object
        """
        RestInstrument.__init__(self, config)
        CameraInstrument.__init__(self, config)
        self.api_command = cast(str, config.get("api_command", "images/camera"))

    def get_last_image(
        self,
    ) -> tuple[int, int, Literal["L", "I;16", "RGB"], bytes | None]:
        try:
            response = self.get()
        except Exception:
            return 0, 0, "L", None
        im = Image.open(io.BytesIO(response.content))
        im_rgb = im.convert("RGB")
        width, height = im_rgb.size
        if width != self.width or height != self.height:
            self.set_resolution(width, height)
        return width, height, "RGB", im_rgb.tobytes()
