from PyQt6.QtCore import QTimer, pyqtSignal, Qt
from PyQt6.QtGui import QImage, QTransform
from PIL import Image, ImageQt
from typing import Optional, Literal, cast
from ..utils.util import yaml_to_qtransform, qtransform_to_yaml
from .instrument import Instrument


class CameraInstrument(Instrument):
    """Class to regroup camera instrument operations"""

    # Signal emitted when a new image is created
    new_image = pyqtSignal(QImage)

    def __init__(self, config: dict):
        """
        :param config: YAML configuration object
        """
        super().__init__()

        # To refresh image regularly, in real-time
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
        self.objective = cast(float, config.get("objective", 1.0))
        self.select_objective(self.objective)

        # Correction matrix
        self.correction_matrix: Optional[QTransform] = None

    def select_objective(self, factor: float):
        """Select an objective with a magnifying factor.

        :param factor: The magnifying factor of the objective (5x, 10x, 20x, 50x...)
        """
        self.objective = factor
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

    @property
    def yaml(self) -> dict:
        """Export settings to a dict for yaml serialization."""
        if self.correction_matrix is not None:
            return {"transform": qtransform_to_yaml(self.correction_matrix)}
        else:
            return {}

    @yaml.setter
    def yaml(self, data: dict):
        """Import settings from a dict."""
        if "transform" in data:
            self.correction_matrix = yaml_to_qtransform(data["transform"])
