from __future__ import annotations

import logging

import numpy

from ..utils.yaml_types import Config
from .camera import CameraInstrument
from .camera_usb_probe import native_resolutions


class CameraUSBInstrument(CameraInstrument):
    """Class to implement the USB cameras, using OpenCv"""

    def __init__(self, config: Config):
        """
        :param config: YAML configuration object
        """
        super().__init__(config)
        import cv2  # Lazy load the module

        self.cv2 = cv2

        index = config.get("index", 0)
        if not isinstance(index, int):
            raise ValueError("index must be an integer in configuration file")
        self.vc = self.__video_capture = cv2.VideoCapture(index)
        if not self.__video_capture.isOpened():
            raise RuntimeError(f"Cannot open USB camera index {index}")

        if self._should_probe_resolutions():
            logging.getLogger("laserstudio").info(
                "Probing supported resolutions for USB camera..."
            )
            thorough = bool(config.get("probe_resolutions_thorough", False))
            self._supported_resolutions = native_resolutions(
                self.__video_capture, thorough=thorough
            )
            logging.getLogger("laserstudio").info(
                "USB camera native resolutions: "
                + ", ".join(f"{w}x{h}" for w, h in self._supported_resolutions)
            )
        else:
            self._supported_resolutions = []

        requested_width = config.get("width")
        requested_height = config.get("height")
        if self._supported_resolutions:
            max_width, max_height = max(
                self._supported_resolutions, key=lambda size: size[0] * size[1]
            )
            self.set_resolution(max_width, max_height)
        elif isinstance(requested_width, int) and isinstance(requested_height, int):
            self.set_resolution(requested_width, requested_height)
        else:
            self._apply_current_capture_resolution()

    def _should_probe_resolutions(self) -> bool:
        return True

    @property
    def supported_resolutions(self) -> list[tuple[int, int]]:
        return list(self._supported_resolutions)

    def _apply_current_capture_resolution(self) -> tuple[int, int]:
        width = int(self.__video_capture.get(self.cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.__video_capture.get(self.cv2.CAP_PROP_FRAME_HEIGHT))
        return self._update_resolution(width, height)

    def set_resolution(self, width: int, height: int) -> tuple[int, int]:
        self.__video_capture.set(self.cv2.CAP_PROP_FRAME_WIDTH, width)
        self.__video_capture.set(self.cv2.CAP_PROP_FRAME_HEIGHT, height)
        for _ in range(3):
            self.__video_capture.read()
        ret, frame = self.__video_capture.read()
        if ret and frame is not None:
            width = int(frame.shape[1])
            height = int(frame.shape[0])
        else:
            width = int(self.__video_capture.get(self.cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.__video_capture.get(self.cv2.CAP_PROP_FRAME_HEIGHT))

        if (
            self._supported_resolutions
            and (width, height) not in self._supported_resolutions
        ):
            logging.getLogger("laserstudio").warning(
                "Requested resolution resolved to "
                f"{width}x{height}, which was not found during probing"
            )
        return self._update_resolution(width, height)

    def _update_resolution(self, width: int, height: int) -> tuple[int, int]:
        if width == self.width and height == self.height:
            return width, height

        self.width = width
        self.height = height
        self._reset_frame_buffers()
        logging.getLogger("laserstudio").info(
            f"USB camera resolution set to {width}x{height}"
        )
        self.parameter_changed.emit("resolution", [width, height])
        return width, height

    def _reset_frame_buffers(self) -> None:
        self._last_frame_accumulator = None
        self._last_frames = []
        self.number_of_averaged_images = 0
        self._last_pos = numpy.zeros((self.width, self.height), dtype=numpy.uint8)
        self.reference_image_accumulators = {}

    def __del__(self):
        self.__video_capture.release()

    def capture_image(self):
        ret, frame = self.__video_capture.read()
        if not ret:
            return None
        frame = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
        if frame.shape[0:2] != (self.height, self.width):
            size = self.width, self.height
            frame = self.cv2.resize(frame, size, interpolation=self.cv2.INTER_AREA)

        return frame.reshape((self.width, self.height, -1))

    @property
    def brightness(self) -> float:
        bri = self.__video_capture.get(self.cv2.CAP_PROP_BRIGHTNESS)
        return float(bri)

    @brightness.setter
    def brightness(self, value: float):
        self.__video_capture.set(self.cv2.CAP_PROP_BRIGHTNESS, value)

    @property
    def contrast(self) -> float:
        con = self.__video_capture.get(self.cv2.CAP_PROP_CONTRAST)
        return float(con)

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
        gain = self.__video_capture.get(self.cv2.CAP_PROP_GAIN)
        return float(gain)

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
        sat = self.__video_capture.get(self.cv2.CAP_PROP_SATURATION)
        return float(sat)

    @saturation.setter
    def saturation(self, value: float):
        self.__video_capture.set(self.cv2.CAP_PROP_SATURATION, value)

    @property
    def fps(self) -> int:
        fps = self.__video_capture.get(self.cv2.CAP_PROP_FPS)
        return int(fps)

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
        gamma = self.__video_capture.get(self.cv2.CAP_PROP_GAMMA)
        return int(gamma)

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

    @property
    def settings(self) -> Config:
        settings = super().settings
        settings["width"] = self.width
        settings["height"] = self.height
        settings["supported_resolutions"] = [
            [width, height] for width, height in self._supported_resolutions
        ]
        return settings

    @settings.setter
    def settings(self, data: Config):
        CameraInstrument.settings.__set__(self, data)  # type: ignore[attr-defined]
        if not self._should_probe_resolutions():
            return
        width = data.get("width")
        height = data.get("height")
        if isinstance(width, int) and isinstance(height, int):
            self.set_resolution(width, height)
