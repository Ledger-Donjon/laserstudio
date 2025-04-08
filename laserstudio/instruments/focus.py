from time import sleep
from PyQt6.QtCore import QThread
from .camera import CameraInstrument
from .stage import StageInstrument, Vector
import scipy.signal
from typing import Optional
import numpy


class FocusSearchSettings:
    """Parameters for the focus search procedure."""

    def __init__(
        self,
        span: float,
        steps: int,
        avg: int,
        multi_peaks: bool,
        best_is_hightest: bool = True,
    ):
        """
        :param span: Z search span, in micrometers. Maximum allowed value is
            1000 µm, for safety purpose. Search will occur in the range
            [z - span / 2, z + span / 2].
        :param steps: Number of search steps. Must be greater or equal to 2.
        :param avg: Image averaging setting. Must be greater or equal to 1.
        :multi_peaks: If True, peak detection is performed, and the peak with
            the higher Z value is considered as the correct focus. This is used
            to distinguish the silicon transistors from the silicon surface. If
            False, the position with the highest image standard deviation is
            kept.
        :best_is_hightest: If True, the best focus is the highest Z value. If False,
            the best focus is the lowest Z value.
        """
        assert span > 0
        assert span < 1000  # In case of bug, prevent large span
        assert steps >= 2
        assert avg >= 1
        self.span = span
        self.steps = steps
        self.avg = avg
        self.multi_peaks = multi_peaks
        self.best_is_hightest = best_is_hightest


class FocusThread(QThread):
    """
    Thread to perform best focus position research by moving a stage and analysing the
    images of a camera.
    """

    def __init__(
        self,
        camera: CameraInstrument,
        stage: StageInstrument,
        coarse: FocusSearchSettings,
        fine: Optional[FocusSearchSettings] = None,
        positions: Optional[list[Vector]] = None,
    ):
        """
        Tries to find optimal stage Z position to get best focus.

        :param camera: Camera instrument for capturing images.
        :param stage: Stage instrument used to modify Z position. At the end of the
            procedure, stage is moved to the best found position.
        :param positions: A list of positions to be scanned. If None, current
            position is used.
        """
        super().__init__()
        self.__camera = camera
        self.__stage = stage
        self.__coarse = coarse
        self.__fine = fine
        self.__positions = positions
        self.best_z = None
        self.best_positions = None

    def run_search(self, settings: FocusSearchSettings):
        """
        Start a research given some search settings.

        :param settings: Focus research settings.
        """
        stage = self.__stage
        z_mid = stage.position.z
        z_max = z_mid + settings.span / 2.0
        z_min = z_mid - settings.span / 2.0
        z_step = (z_max - z_min) / (settings.steps - 1)
        self.__camera.image_averaging = settings.avg
        best_z = None
        best_std_dev = None
        tab = []
        pos: Vector = Vector()

        pos = stage.position
        z_backlash = stage.backlashes[2] if stage.backlashes else 0.0
        stage.move_to(Vector(pos.x, pos.y, z_min - z_backlash), wait=True)

        for i in range(settings.steps):
            z = (z_step * i) + z_min
            pos = stage.position
            stage.move_to(Vector(pos.x, pos.y, z), wait=True)
            # *3: There can be some pipelining in the image processing, there can
            # be latency in the images. This is a bit hacky.
            for _ in range(1):
                self.__camera.clear_averaged_images()
                while self.__camera.average_count < self.__camera.image_averaging:
                    sleep(0.05)

            std_dev = self.__camera.laplacian_std_dev
            tab.append((z, std_dev))
            if (best_std_dev is None) or (std_dev > best_std_dev):
                best_std_dev = std_dev
                best_z = z

        tab = numpy.array(tab)
        peaks = None

        if settings.multi_peaks:
            amplitude = max(tab[:, 1]) - min(tab[:, 1])
            peak_indexes = scipy.signal.find_peaks(
                tab[:, 1], prominence=amplitude * 0.1
            )[0]
            peaks = list(tab[i] for i in peak_indexes)
            # We can get two peaks, one for the silicon surface, and another one
            # for the transistors. This latest has a higher Z value, so we chose
            # the peak with the highest Z.
            best_z = peaks[-1 if settings.best_is_hightest else 0][0]

        if best_z is not None:
            stage.move_to(Vector(pos.x, pos.y, best_z - z_backlash), wait=True)
            stage.move_to(Vector(pos.x, pos.y, best_z), wait=True)
        return (best_z, tab, peaks)

    def run(self):
        """
        Perform focus research, with first coarse settings, and then eventually with fine
        settings.
        """
        avg_prev = self.__camera.image_averaging
        if self.__positions is None:
            self.best_z, self.tab_coarse, self.peaks_coarse = self.run_search(
                self.__coarse
            )
            if self.__fine is not None:
                self.best_z, self.tab_fine, self.peaks_fine = self.run_search(
                    self.__fine
                )
        else:
            self.best_positions = []
            for position in self.__positions:
                self.__stage.move_to(position, wait=True)
                best_z, _, _ = self.run_search(self.__coarse)
                if self.__fine is not None:
                    best_z, _, _ = self.run_search(self.__fine)
                self.best_positions.append(Vector(position.x, position.y, best_z))

        self.__camera.image_averaging = avg_prev  # Restore setting
