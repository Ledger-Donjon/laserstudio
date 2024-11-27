import logging
from .camera import CameraInstrument
from typing import Optional, Literal


class CameraUSBInstrument(CameraInstrument):
    """Class to implement the USB cameras, using OpenCv"""

    def __init__(self, config: dict):
        """
        :param config: YAML configuration object
        """
        super().__init__(config)
        import cv2  # Lazy load the module

        self.cv2 = cv2

        self.__video_capture = cv2.VideoCapture(config.get("index", 0))

        self.width = int(
            config.get("width", self.__video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        )
        self.height = int(
            config.get("height", self.__video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        )

        self.width_um = self.width * self.pixel_size_in_um[0]
        self.height_um = self.height * self.pixel_size_in_um[1]

        logging.getLogger("laserstudio").info(
            f"Camera's resolution {self.width}px; {self.height}px"
        )
        logging.getLogger("laserstudio").info(
            f"Image's dimension {self.width_um}\xa0µm; {self.height_um}\xa0µm (without considering any magnifier)"
        )

    def __del__(self):
        self.__video_capture.release()

    def get_last_image(self) -> tuple[int, int, Literal["L", "RGB"], Optional[bytes]]:
        """Retrieve last captured image"""
        # returns tuple [width, height, fmt, data]. Data is None if acquisition failed.
        ret, frame = self.__video_capture.read()
        if not ret or frame is None:
            return self.width, self.height, "RGB", None
        data = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
        if data.shape != (self.height, self.width, 3):
            size = self.width, self.height
            data = self.cv2.resize(data, size, interpolation=self.cv2.INTER_AREA)
        return self.width, self.height, "RGB", bytes(data)

    @property
    def brightness(self) -> float:
        exp = self.__video_capture.get(self.cv2.CAP_PROP_BRIGHTNESS)
        return float(exp)

    @brightness.setter
    def brightness(self, value: float):
        self.__video_capture.set(self.cv2.CAP_PROP_BRIGHTNESS, value)

    @property
    def contrast(self) -> float:
        exp = self.__video_capture.get(self.cv2.CAP_PROP_CONTRAST)
        return float(exp)

    @contrast.setter
    def contrast(self, value: float):
        self.__video_capture.set(self.cv2.CAP_PROP_CONTRAST, value)

    @property
    def exposure(self) -> float:
        exp = self.__video_capture.get(self.cv2.CAP_PROP_EXPOSURE)
        return float(exp)

    @exposure.setter
    def exposure(self, value: float):
        self.__video_capture.set(self.cv2.CAP_PROP_EXPOSURE, value)

    @property
    def gain(self) -> float:
        exp = self.__video_capture.get(self.cv2.CAP_PROP_GAIN)
        return float(exp)

    @gain.setter
    def gain(self, value: float):
        self.__video_capture.set(self.cv2.CAP_PROP_GAIN, value)

    @property
    def hue(self) -> float:
        exp = self.__video_capture.get(self.cv2.CAP_PROP_HUE)
        return float(exp)

    @hue.setter
    def hue(self, value: float):
        self.__video_capture.set(self.cv2.CAP_PROP_HUE, value)

    @property
    def saturation(self) -> float:
        exp = self.__video_capture.get(self.cv2.CAP_PROP_SATURATION)
        return float(exp)

    @saturation.setter
    def saturation(self, value: float):
        self.__video_capture.set(self.cv2.CAP_PROP_SATURATION, value)

    @property
    def fps(self) -> int:
        exp = self.__video_capture.get(self.cv2.CAP_PROP_FPS)
        return int(exp)

    @fps.setter
    def fps(self, value: int):
        self.__video_capture.set(self.cv2.CAP_PROP_FPS, value)

    @property
    def sharpness(self) -> int:
        exp = self.__video_capture.get(self.cv2.CAP_PROP_SHARPNESS)
        return int(exp)

    @sharpness.setter
    def sharpness(self, value: int):
        self.__video_capture.set(self.cv2.CAP_PROP_SHARPNESS, value)

    @property
    def gamma(self) -> int:
        exp = self.__video_capture.get(self.cv2.CAP_PROP_GAMMA)
        return int(exp)

    @gamma.setter
    def gamma(self, value: int):
        self.__video_capture.set(self.cv2.CAP_PROP_GAMMA, value)

    def set_gain(self, low: int, high: int):
        # TODO: Untested yet
        gain = (low + high) // 2
        self.__video_capture.set(self.cv2.CAP_PROP_EXPOSURE, gain)

    def gain_autoset(self) -> tuple[int, int]:
        # TODO: Untested yet
        exp = self.__video_capture.get(self.cv2.CAP_PROP_EXPOSURE)
        exp = int(exp)
        return exp, exp
