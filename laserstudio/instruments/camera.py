from PyQt6.QtCore import QTimer, pyqtSignal, Qt
from PyQt6.QtGui import QImage, QTransform
from PIL import Image, ImageQt
from typing import Optional, Literal, cast
from ..utils.util import yaml_to_qtransform, qtransform_to_yaml
from .instrument import Instrument
from .shutter import ShutterInstrument, TicShutterInstrument
import logging
import numpy


class CameraInstrument(Instrument):
    """Class to regroup camera instrument operations"""

    # Signal emitted when a new image is created
    new_image = pyqtSignal(QImage)

    def __init__(self, config: dict):
        """
        :param config: YAML configuration object
        """
        super().__init__(config=config)

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

        # Shutter
        shutter = config.get("shutter")
        self.shutter: Optional[ShutterInstrument] = None
        if type(shutter) is dict and shutter.get("enable", True):
            try:
                if (device_type := shutter.get("type")) == "TIC":
                    self.shutter = TicShutterInstrument(shutter)
                else:
                    logging.getLogger("laserstudio").error(
                        f"Unknown Shutter type {device_type}. Skipping device."
                    )
            except Exception as e:
                logging.getLogger("laserstudio").warning(
                    f"Shutter is enabled but device could not be created: {str(e)}... Skipping."
                )

        # Whtie and black levels adjustment
        self.black_level = 0.0
        self.white_level = 1.0

        # Image averaging
        self._last_frame_accumulator: numpy.ndarray = numpy.zeros(
            self.width * self.height, dtype=numpy.uint64
        )
        # The number of images to average
        self._image_averaging = 1
        # The number of images that have been averaged
        self.number_of_averaged_images = 0

        # Window averaging makes to store all averaged image to make a 'rotating' average
        # When the number of images to average is hit, and a new frame is retrieved,
        # the oldest one is removed from the accumulator and the new one is added.
        self.windowed_averaging = True
        self._last_frames: list[numpy.ndarray] = [
            numpy.zeros(self.width * self.height, dtype=numpy.uint16)
        ] * self._image_averaging

        self.show_negative_values = True

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

    def get_last_image(
        self,
    ) -> tuple[int, int, Literal["L", "I;16", "RGB"], Optional[bytes]]:
        """
        To be overridden by the subclasses or CameraInstrument

        :return: a tuple containing: the width, height, color_mode, and data of the picture.
            color_mode is data from PIL.Image module.
        """
        return self.width, self.height, "L", None

    @property
    def image_averaging(self) -> int:
        """
        Returns the number of images that must be averaged.
        """
        return self._image_averaging

    @image_averaging.setter
    def image_averaging(self, value: int):
        """
        Sets the number of images that must be averaged.
        """
        if self.windowed_averaging:
            if len(self._last_frames) > value:
                # Drop the oldest frames (at the begining of the array)
                to_substract = self._last_frames[: len(self._last_frames) - value]
                self._last_frames = self._last_frames[len(self._last_frames) - value :]
                self._last_frame_accumulator -= sum(to_substract)
                self.number_of_averaged_images -= len(to_substract)
        else:
            self.clear_averaged_images()

        self._image_averaging = value

    def clear_averaged_images(self):
        """
        Clears the list of averaged images.
        """
        self._last_frames = []
        self._last_frame_accumulator = numpy.zeros(
            self.width * self.height, dtype=numpy.uint64
        )
        self.number_of_averaged_images = 0

    def accumulate_frame(self, new_frame: numpy.ndarray):
        """
        Accumulates the given frame and removes the oldest one
          if windowed averaging is active.
        """
        if not self.windowed_averaging:
            if self.number_of_averaged_images == self._image_averaging:
                # Discarding the new frame from accumulation
                return
        if self._image_averaging == self.number_of_averaged_images:
            # The list is full, we can remove the oldest frame
            self._last_frame_accumulator -= self._last_frames.pop(0)
            self.number_of_averaged_images -= 1
        # Add the new frame in the accumulator and the list
        self._last_frames.append(new_frame)
        self._last_frame_accumulator += new_frame
        self.number_of_averaged_images += 1

    @property
    def average_count(self) -> int:
        """
        Returns the number of images that have been averaged.
        """
        return self.number_of_averaged_images

    def apply_levels(self, image: numpy.ndarray) -> numpy.ndarray:
        """
        Apply the black and white levels to the image before displaying it.

        :param image: The image to apply the levels to.
        :return: The image with the levels applied.
        """
        max = numpy.iinfo(image.dtype).max
        type_ = image.dtype
        image = image - self.black_level * max
        image = (
            image / (self.white_level - self.black_level)
            if self.white_level - self.black_level != 0
            else image
        )
        return image.clip(0, max).astype(type_)

    def compute_histogram(self, frame: numpy.ndarray):
        # Compute histogram of last image
        return numpy.histogram(
            frame,
            bins=150,
            range=(0, numpy.iinfo(frame.dtype).max),
        )

    def histogram_to_string(self, hist: numpy.ndarray, nlines=2):
        bar = " ▁▂▃▄▅▆▇█"
        hist = nlines * (hist / max(hist)) * (len(bar) - 1)
        hists = []
        for i in range(nlines):
            offset = i * len(bar)
            val = [int(i) - offset for i in hist]
            val = [max(0, min(len(bar) - 1, i)) for i in val]
            hists.append("".join(bar[i] for i in val))
        return hists[::-1]

    def levels_to_string(self):
        white_pos = int(150 * self.white_level)
        black_pos = int(150 * self.black_level)

        return " " * black_pos + "^", " " * white_pos + "^"

    def take_reference_image(self, do_take: bool):
        """
        Take a reference image to substract from the next frames.
        """
        if do_take:
            self.reference_image_accumulator = self._last_frame_accumulator.copy()
        else:
            self.reference_image_accumulator = None

    def substract_reference_image(
        self,
    ) -> tuple[numpy.ndarray, Optional[numpy.ndarray]]:
        """Substract the reference_image_accumulator from the current accumulator"""
        if self.reference_image_accumulator is None:
            """The reference image is not yet defined"""
            self._last_pos = self._last_frame_accumulator
            self._last_neg = None
        else:
            self._last_pos = (
                (self._last_frame_accumulator - self.reference_image_accumulator)
                .astype(numpy.int64)
                .clip(0)
                .astype(numpy.uint64)
            )
            self._last_neg = (
                (self.reference_image_accumulator - self._last_frame_accumulator)
                .astype(numpy.int64)
                .clip(0)
                .astype(numpy.uint64)
            )
        return self._last_pos, self._last_neg

    @property
    def last_frame(self) -> numpy.ndarray:
        """
        Return the frame that should be analysed by histogram computation
        """
        pos = self._last_pos
        neg = self._last_neg
        return self.construct_display_image(pos, neg)

    def construct_display_image(
        self, pos: numpy.ndarray, neg: Optional[numpy.ndarray]
    ) -> numpy.ndarray:
        """
        Construct the display image from the positive and negative images.
        """
        pos_16 = (
            (pos * (4.0 / self.average_count))
            .clip(
                min=numpy.iinfo(numpy.uint16).min,
                max=numpy.iinfo(numpy.uint16).max,
            )
            .astype(numpy.uint16)
        )
        if neg is None:
            return pos_16

        neg_16 = (
            (neg * (4.0 / self.average_count))
            .clip(
                min=numpy.iinfo(numpy.uint16).min,
                max=numpy.iinfo(numpy.uint16).max,
            )
            .astype(numpy.uint16)
        )
        zer_16 = numpy.zeros((self.height, self.width, 1), dtype=numpy.uint16)
        pos_16 = pos_16.reshape(zer_16.shape)
        neg_16 = neg_16.reshape(zer_16.shape)
        stacked = numpy.stack([neg_16, pos_16, zer_16], axis=2)

        return stacked.astype(numpy.uint8).reshape(self.height * self.width * 3)

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
