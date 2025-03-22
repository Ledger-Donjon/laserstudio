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
        self._last_frame_accumulator: Optional[numpy.ndarray] = None
        # The number of images to average
        self._image_averaging = 1
        # The number of images that have been averaged
        self.number_of_averaged_images = 0

        # Window averaging makes to store all averaged image to make a 'rotating' average
        # When the number of images to average is hit, and a new frame is retrieved,
        # the oldest one is removed from the accumulator and the new one is added.
        self.windowed_averaging = True
        self._last_frames: list[numpy.ndarray] = []

        # Reference image feature
        self.reference_image_accumulator: Optional[numpy.ndarray] = None
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

    def capture_image(self) -> Optional[numpy.ndarray]:
        """
        To be overridden by the subclasses or CameraInstrument

        :return: a ndarray corresponding to the image. None if the acquisition failed.
        """
        return None

    def get_last_image(
        self,
    ) -> tuple[int, int, Literal["L", "I;16", "RGB"], Optional[bytes]]:
        """
        Capture an image and construct a Gray, 16bit Gray or RGB byte array.

        :return: a tuple containing: the width, height, color_mode, and data of the picture.
            color_mode is data from PIL.Image module.
        """
        frame = self.capture_image()
        if frame is None:
            return self.width, self.height, "L", None

        # Put the frame in the accumulator
        self.accumulate_frame(frame)
        assert self._last_frame_accumulator is not None

        # Apply the subtraction of reference image
        pos, neg = self.substract_reference_image()
        # Construct a frame from substracted values
        frame = self.construct_display_image(pos, neg)
        # Apply levels
        frame = self.apply_levels(frame)
        mode = "RGB" if frame.shape[-1] == 3 else "L"
        return self.width, self.height, mode, frame.tobytes()

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
        if self._last_frame_accumulator is not None and self.windowed_averaging:
            # In the case we are in windowed_average mode and we have already accumulated images
            if len(self._last_frames) > value:
                # We reduce the number of images to average
                # Drop the oldest frames (at the begining of the array)
                to_substract = self._last_frames[: len(self._last_frames) - value]
                self._last_frames = self._last_frames[len(self._last_frames) - value :]
                self._last_frame_accumulator -= sum(to_substract)
                self.number_of_averaged_images -= len(to_substract)
                assert len(self._last_frames) == self.number_of_averaged_images
                assert (
                    len(self._last_frames) == value
                ), f"List of frames {self._last_frames} is inconsistent with new number of image_averaging {value}"
        else:
            self.clear_averaged_images()

        self._image_averaging = value

    def clear_averaged_images(self):
        """
        Clears the list of averaged images.
        """
        self._last_frames = []
        self._last_frame_accumulator = None
        self.number_of_averaged_images = 0

    def accumulate_frame(self, new_frame: numpy.ndarray):
        """
        Accumulates the given frame and removes the oldest one
          if windowed averaging is active.
        """
        # We make sure that we have an image in the accumulator
        if self._last_frame_accumulator is None:
            self._last_frame_accumulator = new_frame.astype(numpy.uint64, copy=True)
            self.number_of_averaged_images = 1
            if self.windowed_averaging:
                self._last_frames = [new_frame]
            return

        if not self.windowed_averaging:
            if self.number_of_averaged_images == self._image_averaging:
                # Discarding the new frame from accumulation
                return

        if self._image_averaging == self.number_of_averaged_images:
            # The list is full, we can remove the oldest frame
            if self.windowed_averaging:
                self._last_frame_accumulator -= self._last_frames.pop(0)
                self.number_of_averaged_images -= 1
        # Add in the list
        if self.windowed_averaging:
            self._last_frames.append(new_frame)

        # We accumulate the value of the frame
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

    def substract_reference_image(self):
        """Substract the reference_image_accumulator from the current accumulator"""
        assert self._last_frame_accumulator is not None
        if self.reference_image_accumulator is None:
            self._last_pos = self._last_frame_accumulator
            self._last_neg = None
            return self._last_pos, self._last_neg

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
        self, pos: numpy.ndarray, neg: Optional[numpy.ndarray] = None
    ) -> numpy.ndarray:
        """
        Construct the display image from the positive and negative images.
        """
        pos_8 = (
            (pos / self.average_count)
            .clip(
                min=numpy.iinfo(numpy.uint8).min,
                max=numpy.iinfo(numpy.uint8).max,
            )
            .astype(numpy.uint8)
        )
        if neg is None:
            return pos_8

        # There is a negative value, which means that we are in differential analysis mode
        neg_8 = (
            (
                (neg / self.average_count)
                .clip(
                    min=numpy.iinfo(numpy.uint8).min,
                    max=numpy.iinfo(numpy.uint8).max,
                )
                .astype(numpy.uint8)
            )
            if self.show_negative_values
            else numpy.zeros(pos_8.shape, dtype=numpy.uint8)
        )

        if pos_8.shape[-1] == 3:
            return pos_8 + neg_8

        zer_8 = numpy.zeros((self.width, self.height, 1), dtype=numpy.uint8)
        stacked = numpy.stack([neg_8, pos_8, zer_8], axis=2)
        return stacked.reshape(self.width, self.height, 3)

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
