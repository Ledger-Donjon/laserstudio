from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from PyQt6.QtGui import QImage
from PIL import Image, ImageQt
from typing import Tuple, Optional, Literal
import logging


class CameraInstrument(QObject):
    """Class to regroup camera instrument operations"""

    # Signal emitted when a new image is created
    new_image = pyqtSignal(QImage, name="newImage")

    def __init__(self, config: dict):
        """
        :param config: YAML configuration object
        """
        super().__init__()

        # To refresh image regularly, in real-time
        self._timer = QTimer()
        self._timer.timeout.connect(self.get_last_qImage)
        self._timer.start(50)

        self.width = 640
        self.height = 512

    def get_last_qImage(self) -> QImage:
        width, height, mode, data = self.get_last_image()
        size = (width, height)
        # PIL.ImageQt.ImageQt is a subclass of QImage
        if data is None:
            im = Image.new("L", size=size)
        else:
            im = Image.frombytes(mode=mode, data=data, size=size)
        qImage = ImageQt.ImageQt(im)
        self.new_image.emit(qImage)
        return qImage

    def get_last_image(self) -> Tuple[int, int, Literal["L", "RGB"], Optional[bytes]]:
        """
        To be overridden by the subclasses or CameraInstrument

        :return: a tuple containing: the width, height, color_mode, and data of the picture.
            color_mode is data from PIL.Image module.
        """
        return self.width, self.height, "L", None


class CameraUSBInstrument(CameraInstrument):
    """Class to implement the USB cameras, using OpenCv"""

    def __init__(self, config: dict):
        """
        :param config: YAML configuration object
        """
        super().__init__(config)
        import cv2  # Lazy load the module

        self.cv2 = cv2

        self.__video_capture = cv2.VideoCapture(config.get("num", 0))

        self.width = int(
            config.get("width", self.__video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        )
        self.height = int(
            config.get("height", self.__video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        )
        logging.info(f"{self.width}; {self.height}")

    def __del__(self):
        self.__video_capture.release()

    def get_last_image(self) -> Tuple[int, int, Literal["L", "RGB"], Optional[bytes]]:
        """Retrieve last captured image"""
        # returns Tuple [width, height, fmt, data]. Data is None if acquisition failed.
        ret, frame = self.__video_capture.read()
        if not ret or frame is None:
            return self.width, self.height, "RGB", None
        data = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
        if data.shape != (self.height, self.width, 3):
            size = self.width, self.height
            data = self.cv2.resize(data, size, interpolation=self.cv2.INTER_AREA)
        return self.width, self.height, "RGB", bytes(data)
