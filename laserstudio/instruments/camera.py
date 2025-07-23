import os
import logging
from typing import Optional, Literal, cast
import numpy
import cv2
from PyQt6.QtCore import QTimer, pyqtSignal, Qt
from PyQt6.QtGui import QImage, QTransform
from PIL import Image, ImageQt
from ..utils.util import yaml_to_qtransform, qtransform_to_yaml
from .instrument import Instrument
from .shutter import ShutterInstrument, TicShutterInstrument


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
            self.refresh_interval, Qt.TimerType.CoarseTimer, self.get_last_qimage
        )

        # Image size in pixels
        self.width = cast(int, config.get("width", 640))
        self.height = cast(int, config.get("height", 512))

        # Image flip
        self.invert_vertical = cast(bool, config.get("invert_vertical", False))
        self.invert_horizontal = cast(bool, config.get("invert_horizontal", False))

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

        self._last_neg = None
        self._last_pos = numpy.zeros((self.width, self.height), dtype=numpy.uint8)

        # Window averaging makes to store all averaged image to make a 'rotating' average
        # When the number of images to average is hit, and a new frame is retrieved,
        # the oldest one is removed from the accumulator and the new one is added.
        self.windowed_averaging = True
        self._last_frames: list[numpy.ndarray] = []

        # Reference image feature
        self.reference_image_accumulators: dict[str, numpy.ndarray] = {}
        self.current_reference_image = "Reference 0"
        self.show_negative_values = True

        # The value of a white pixel
        self.white_value = 2**8 - 1

    @property
    def reference_image_accumulator(self) -> Optional[numpy.ndarray]:
        """
        Returns the current reference image.

        :return: The current reference image, or None if no reference image is set.
        """
        return self.reference_image_accumulators.get(self.current_reference_image)

    @reference_image_accumulator.setter
    def reference_image_accumulator(self, value: Optional[numpy.ndarray]):
        if (
            value is None
            and self.current_reference_image in self.reference_image_accumulators
        ):
            del self.reference_image_accumulators[self.current_reference_image]
        elif value is not None:
            self.reference_image_accumulators[self.current_reference_image] = value
        # Do nothing...

    @property
    def last_frame_accumulator(self) -> Optional[numpy.ndarray]:
        """
        Returns the last frame accumulator. See accumulate_frame, and image_averaging for more details.

        :return: The last frame accumulator (eg, averaged), or None if no frame has been accumulated yet.
        """
        return (
            self._last_frame_accumulator.copy()
            if self._last_frame_accumulator is not None
            else None
        )

    def select_objective(self, factor: float):
        """Select an objective with a magnifying factor.

        :param factor: The magnifying factor of the objective (5x, 10x, 20x, 50x...)
        """
        self.objective = factor
        self.width_um = self.width * self.pixel_size_in_um[0] / factor
        self.height_um = self.height * self.pixel_size_in_um[1] / factor

    def get_last_qimage(self) -> QImage:
        """
        Returns the last image as a QImage.

        :return: The last image as a QImage.
        """
        # PIL.ImageQt.ImageQt is a subclass of QImage
        qimage = ImageQt.ImageQt(self.get_last_pil_image())
        self.new_image.emit(qimage)
        QTimer.singleShot(
            self.refresh_interval, Qt.TimerType.CoarseTimer, self.get_last_qimage
        )
        return qimage

    def get_last_pil_image(self) -> Image.Image:
        """
        Returns the last image as a PIL image.

        :return: The last image as a PIL image.
        """
        width, height, mode, data = self.get_last_image()
        size = (width, height)
        if data is None:
            im = Image.new("L", size=size)
        else:
            im = Image.frombytes(mode=mode, data=data, size=size)
        return im

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

        frame = frame.reshape((self.height, self.width, -1))
        if self.invert_horizontal:
            # Invert the frame horizontally
            frame = numpy.fliplr(frame)
        if self.invert_vertical:
            # Invert the frame vertically
            frame = numpy.flipud(frame)

        # Put the frame in the accumulator
        self.accumulate_frame(frame)
        assert self._last_frame_accumulator is not None

        # Apply the subtraction of reference image
        pos, neg = self.substract_reference_image()

        # Apply levels
        pos = self.apply_levels(pos)
        if neg is not None:
            neg = self.apply_levels(neg)

        # Construct a frame from substracted values
        frame = self.construct_display_image(pos, neg)
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
        self._image_averaging = value
        self.clear_averaged_images()

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
    def is_average_valid(self) -> bool:
        """
        Returns True if the number of averaged images is sufficient.
        """
        return self.average_count >= self.image_averaging

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
        max = self.white_value * self.average_count
        type_ = image.dtype

        image = image - self.black_level * max
        image = (
            image / (self.white_level - self.black_level)
            if self.white_level - self.black_level != 0
            else image
        )
        return image.clip(min=0).astype(type_)

    def compute_histogram(self, frame: numpy.ndarray, width: int = -1):
        """
        Computes the histogram of the given frame.

        :param frame: The frame to compute the histogram of.
        :param width: The width of the histogram.
        :return: The histogram.
        """
        if width <= 0:
            width = os.get_terminal_size().columns - 2

        # Compute histogram of last image
        return numpy.histogram(
            frame,
            bins=width,
            range=(0, numpy.iinfo(frame.dtype).max),
        )

    def histogram_to_string(self, hist: numpy.ndarray, nlines=2):
        """
        Returns the histogram as a string representation.

        :param hist: The histogram to convert to a string.
        :param nlines: The number of lines to print (height of the histogram).
        :return: A list of strings representing the histogram (one per line).
        """
        bar = " ▁▂▃▄▅▆▇█"
        hist = nlines * (hist / max(hist)) * (len(bar) - 1)
        hists = []
        for i in range(nlines):
            offset = i * len(bar)
            val = [int(i) - offset for i in hist]
            val = [max(0, min(len(bar) - 1, i)) for i in val]
            hists.append("".join(bar[i] for i in val))
        return hists[::-1]

    def levels_to_string(self, width: int = -1) -> tuple[str, str]:
        """
        Returns the black and white levels
            as a tuple of strings reprensenting the position of the
            black and white levels with markers (^).

        :param width: The width of the terminal.
        :return: A tuple of strings reprensenting the position of the
            black and white levels with markers (^).
        """
        if width <= 0:
            width = os.get_terminal_size().columns - 2
        white_pos = int(width * self.white_level)
        black_pos = int(width * self.black_level)
        return " " * black_pos + "^", " " * white_pos + "^"

    def show_histogram_terminal(
        self,
        frame: Optional[numpy.ndarray] = None,
        nlines: int = 5,
        nbins: int = 0,
    ):
        """
        Prints the histogram of the last frame in the terminal.

        :param frame: The frame to compute the histogram of.
        :param nlines: The number of lines to print.
        :param nbins: The number of bins to use for the histogram.
        """
        if nbins <= 0:
            nbins = os.get_terminal_size().columns - 2
        hists = self.histogram_to_string(
            self.compute_histogram(frame=frame or self.last_frame, width=nbins)[0],
            nlines=nlines,
        )
        print("⸢" + hists[0] + "⸣")
        for hist in hists[1:-1]:
            print("|" + hist + "|")
        print("⸤" + hists[-1] + "⸥")

    def show_levels_terminal(self, width: int = -1):
        """
        Prints the black and white levels in the terminal.

        :param width: The width of the terminal.
        """
        if width <= 0:
            width = os.get_terminal_size().columns - 2
        levels = self.levels_to_string(width=width)
        print("B" + levels[0])
        print("W" + levels[1])

    def take_reference_image(self, do_take: bool):
        """
        Take a reference image to substract from the next frames.

        :param do_take: True if a reference image should be taken,
            False if the reference image should be reset.
        """
        if do_take and self._last_frame_accumulator is not None:
            self.reference_image_accumulator = self._last_frame_accumulator.copy()
        else:
            self.reference_image_accumulator = None

    def substract_reference_image(self) -> tuple[numpy.ndarray, Optional[numpy.ndarray]]:
        """
        Substract the reference_image_accumulator from the current accumulator

        :return: A tuple containing the positive and negative images.
        """
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
        Return the frame that should be analysed or displayed.

        :return: The frame that should be analysed or displayed.
        """
        pos = self._last_pos
        neg = self._last_neg
        return self.construct_display_image(pos, neg)

    def construct_display_image(
        self, pos: numpy.ndarray, neg: Optional[numpy.ndarray] = None
    ) -> numpy.ndarray:
        """
        Construct the display image from the positive and negative images.

        :param pos: The positive image.
        :param neg: The negative image.
        :return: The display image.
        """
        average_count = self.average_count
        # In some cases (when clear_average_images has been called, average_count may be equal 0)
        # pos and neg should be coming from _last_pos and _last_neg, so bound to self.image_averaging
        if average_count == 0:
            average_count = self.image_averaging
        pos_8 = (
            (pos / average_count)
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
                (neg / average_count)
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
        stacked = numpy.stack(
            [
                neg_8.reshape(self.width, self.height, 1),
                pos_8.reshape(self.width, self.height, 1),
                zer_8,
            ],
            axis=2,
        )
        return stacked.reshape(self.width, self.height, 3)

    @property
    def settings(self) -> dict:
        """Export settings to a dict for yaml serialization."""
        settings = super().settings
        if self.correction_matrix is not None:
            settings["transform"] = qtransform_to_yaml(self.correction_matrix)
        settings["white_level"] = self.white_level
        settings["black_level"] = self.black_level
        settings["shutter"] = self.shutter.settings if self.shutter else None
        settings["image_averaging"] = self.image_averaging
        settings["windowed_averaging"] = self.windowed_averaging
        settings["objective"] = self.objective

        return settings

    @settings.setter
    def settings(self, data: dict):
        """Import settings from a dict."""
        Instrument.settings.__set__(self, data)
        if "transform" in data:
            self.correction_matrix = yaml_to_qtransform(data["transform"])
        if "white_level" in data:
            self.white_level = data["white_level"]
            self.parameter_changed.emit("white_level", data["white_level"])
        if "black_level" in data:
            self.black_level = data["black_level"]
            self.parameter_changed.emit("black_level", data["black_level"])
        if "shutter" in data and self.shutter is not None:
            self.shutter.settings = data["shutter"]
            self.parameter_changed.emit("shutter", data["shutter"])
        if "image_averaging" in data:
            self.image_averaging = data["image_averaging"]
            self.parameter_changed.emit("image_averaging", data["image_averaging"])
        if "windowed_averaging" in data:
            self.windowed_averaging = data["windowed_averaging"]
            self.parameter_changed.emit(
                "windowed_averaging", data["windowed_averaging"]
            )
        if "objective" in data:
            self.select_objective(data["objective"])
            self.parameter_changed.emit("objective", data["objective"])

    @property
    def laplacian_std_dev(self) -> float:
        """
        Return the standard deviation of the Laplacian operator on the last image.

        :return: The standard deviation of the Laplacian operator on the last image.
        """
        if (last_frame := self.last_frame) is None:
            return 0.0
        # KSIZE (3): Aperture size used to compute the
        #   second-derivative filters. See getDerivKernels for details.
        #   The size must be positive and odd.
        dst = cv2.Laplacian(last_frame, cv2.CV_8U, ksize=3)
        _, std_dev = cv2.meanStdDev(dst)
        return float(std_dev[0][0])
