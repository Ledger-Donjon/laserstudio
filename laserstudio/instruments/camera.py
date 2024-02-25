from PyQt6.QtCore import QTimer, QObject, pyqtSignal, Qt
from PyQt6.QtGui import QImage
from PIL import Image, ImageQt
from typing import Optional, Literal, cast


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
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.get_last_qImage)
        self.refresh_interval = cast(int, config.get("refresh_interval_ms", 200))

        QTimer.singleShot(
            self.refresh_interval, Qt.TimerType.CoarseTimer, self.get_last_qImage
        )

        self.width = cast(int, config.get("width", 640))
        self.height = cast(int, config.get("height", 512))

        # Unit factor to apply in order to get coordinates in micrometers
        self.pixel_size_in_um = cast(
            list[float], config.get("pixel_size_in_um", [1.0, 1.0])
        )

        # Objective
        objective = cast(float, config.get("objective", 1.0))

        self.select_objective(objective)

    def select_objective(self, factor: float):
        """Select an objective with a magnifying factor.

        :param factor: The magnifying factor of the objective (5x, 10x, 20x, 50x...)
        """
        self.width_um = self.width * self.pixel_size_in_um[0] / factor
        self.height_um = self.height * self.pixel_size_in_um[1] / factor

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

        QTimer.singleShot(
            self.refresh_interval, Qt.TimerType.CoarseTimer, self.get_last_qImage
        )
        return qImage

    def get_last_image(self) -> tuple[int, int, Literal["L", "RGB"], Optional[bytes]]:
        """
        To be overridden by the subclasses or CameraInstrument

        :return: a tuple containing: the width, height, color_mode, and data of the picture.
            color_mode is data from PIL.Image module.
        """
        return self.width, self.height, "L", None
