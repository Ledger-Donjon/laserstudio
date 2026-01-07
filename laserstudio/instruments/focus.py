from PyQt6.QtCore import QThread, pyqtSignal
from .stage import StageInstrument, Vector
from .instrument import Instrument
import scipy.signal
from typing import Optional, Any, TYPE_CHECKING
import numpy
from PyQt6.QtCore import QCoreApplication
from pystages import Autofocus

if TYPE_CHECKING:
    from .camera import CameraInstrument


class FocusSearchSettings:
    """Parameters for the focus search procedure."""

    def __init__(
        self,
        span: float,
        steps: int,
        averaging: int,
        multi_peaks: bool,
        best_is_highest_z: bool = True,
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
        assert span > 0, "Span must be positive"
        assert steps >= 2, "Steps must be greater or equal to 2"
        assert averaging >= 1, "Image averaging must be greater or equal to 1"
        self.span = span
        self.steps = steps
        self.avg = averaging
        self.multi_peaks = multi_peaks
        self.best_is_highest_z = best_is_highest_z


class FocusThread(QThread):
    """
    Thread to perform best focus position research by moving a stage and analysing the
    images of a camera.
    """

    # Signal to be emitted when the a new point of focus is found.
    new_point = pyqtSignal(float, float)

    def __init__(
        self,
        camera: "CameraInstrument",
        stage: StageInstrument,
        coarse: FocusSearchSettings,
        fine: Optional[FocusSearchSettings] = None,
        positions: Optional[list[Vector]] = None,
        objective: float = 1.0,
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
        self.z_mid = None
        self.best_z = None
        self.best_positions = None
        self.tab_coarse = None
        self.peaks_coarse = None
        self.tab_fine = None
        self.peaks_fine = None
        self.objective = objective

    def z_range(
        self,
        z_mid: Optional[float] = None,
        settings: Optional[FocusSearchSettings] = None,
    ) -> tuple[float, float]:
        """
        Return the Z range of the focus search.

        :return: Z range of the focus search.
        """
        z_mid = z_mid or self.__stage.position.z
        settings = settings or self.__coarse
        return (
            z_mid - (settings.span / 2.0) / self.objective,
            z_mid + (settings.span / 2.0) / self.objective,
        )

    def run_search(self, settings: FocusSearchSettings):
        """
        Start a research given some search settings.

        :param settings: Focus research settings.
        """
        stage = self.__stage
        z_mid = (pos := stage.position).z
        z_min, z_max = self.z_range(z_mid, settings)
        z_step = (z_max - z_min) / (settings.steps - 1)
        self.__camera.image_averaging = settings.avg
        best_z = None
        best_std_dev = None
        tab = []

        z_backlash = stage.backlashes[2] if stage.backlashes else 0.0
        stage.move_to(Vector(pos.x, pos.y, z_min - z_backlash), wait=True)

        print(
            f"Focus search at {pos.xy}: "
            f"{z_min:.2f} to {z_max:.2f} with {settings.steps} steps, "
            f"averaging {settings.avg} images"
        )
        for i in range(settings.steps):
            z = (z_step * i) + z_min
            print(f"Step {i} / {settings.steps}: {z:.2f}")
            pos = stage.position
            stage.move_to(Vector(pos.x, pos.y, z), wait=True)
            # *3: There can be some pipelining in the image processing, there can
            # be latency in the images. This is a bit hacky.
            for _ in range(1):
                self.__camera.clear_averaged_images()
                while self.__camera.average_count < self.__camera.image_averaging:
                    QCoreApplication.processEvents()
            std_dev = self.__camera.laplacian_std_dev
            tab.append((z, std_dev))
            self.new_point.emit(z, std_dev)
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
            if len(peaks) == 0:
                best_z = z_mid
            else:
                # We can get two peaks, one for the silicon surface, and another one
                # for the transistors. This latest has a higher Z value, so we chose
                # the peak with the highest Z.
                best_z = peaks[-1 if settings.best_is_highest_z else 0][0]

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


class FocusInstrument(Instrument):
    """
    Focus instrument. This vitual instrument is used to perform focus research on a
    stage using a camera.
    """

    def __init__(
        self, config: dict, camera: "CameraInstrument", stage: StageInstrument
    ):
        super().__init__(config)
        self.camera = camera
        self.stage = stage

        # Autofocus helper from pystage
        self.autofocus_helper = Autofocus()

        # Magic Focus
        # Set when a focus search is running, then cleared.
        # This is used to prevent launching two search threads at the same time.
        self.focus_thread: Optional[FocusThread] = None

        self.fine_focus_settings: Optional[FocusSearchSettings] = None
        self.coarse_focus_settings: Optional[FocusSearchSettings] = None

        # Magic focus settings
        if "fine" in config:
            self.fine_focus_settings = FocusSearchSettings(**config["fine"])
        if "coarse" in config:
            self.coarse_focus_settings = FocusSearchSettings(**config["coarse"])

    def clear(self):
        """
        Clear all focused points
        """
        self.autofocus_helper.clear()
        self.parameter_changed.emit(
            "autofocus_points", self.autofocus_helper.registered_points
        )

    def register(self, position: Optional[tuple[float, float, float]] = None):
        """
        Register a new focused point.

        :param position: Position to register.
        """
        if position is None:
            position = tuple(self.stage.position.data)
        self.autofocus_helper.register(position[0], position[1], position[2])
        self.parameter_changed.emit(
            "autofocus_points", self.autofocus_helper.registered_points
        )

    def autofocus(self, register_point: bool = False):
        if self.stage is None:
            return
        pos = self.stage.position
        if register_point:
            self.register((pos.x, pos.y, pos.z))
            return
        if len(self.autofocus_helper.registered_points) < 3:
            return
        z = self.autofocus_helper.focus(pos.x, pos.y)
        assert abs(z - pos.z) < 500, (
            f"Prevent autofocus from moving more than 500 µm ({abs(z - pos.z)} µm was requested)"
        )
        if self.stage.backlashes and len(self.stage.backlashes) > 2:
            # Move to the position with backlash compensation
            self.stage.move_to(
                Vector(pos.x, pos.y, z - self.stage.backlashes[2]), wait=True
            )
        self.stage.move_to(Vector(pos.x, pos.y, z), wait=True)

    def magic_focus_state(self):
        if (
            self.stage is None
            or self.camera is None
            or (t := self.focus_thread) is None
        ):
            return {"existing": False}
        res: dict[str, Any] = {
            "existing": True,
            "running": t.isRunning(),
            "finished": t.isFinished(),
        }
        if t.best_z is not None:
            res["best_z"] = t.best_z
        if t.tab_coarse is not None:
            res["tab_coarse"] = str(t.tab_coarse)
        if t.tab_fine is not None:
            res["tab_fine"] = str(t.tab_fine)
        return res

    def parse_parameters(self, parameters: dict):
        if "coarse" in parameters:
            coarse_focus_settings = FocusSearchSettings(**parameters["coarse"])
        else:
            coarse_focus_settings = None
        if "fine" in parameters:
            fine_focus_settings = FocusSearchSettings(**parameters["fine"])
        else:
            fine_focus_settings = None
        return coarse_focus_settings, fine_focus_settings

    def magic_focus(
        self,
        coarse: Optional[FocusSearchSettings] = None,
        fine: Optional[FocusSearchSettings] = None,
        parameters: Optional[dict] = None,
    ):
        """
        Estimates automatically the correct focus by moving the stage and analysing the
        resulting camera image. This is executed in a thread.
        """
        if self.focus_thread is not None and self.focus_thread.isRunning():
            # Focus search already running
            print("Focus search already running")
            return self.focus_thread

        if parameters is not None:
            coarse, fine = self.parse_parameters(parameters)

        if coarse is None:
            coarse = self.coarse_focus_settings or FocusSearchSettings(
                span=4000,
                steps=20,
                averaging=5,
                multi_peaks=True,
                best_is_highest_z=False,
            )
        if fine is None:
            fine = self.fine_focus_settings

        # Adapt range depending on currently selected microscope objective.
        objective = self.camera.objective
        t = FocusThread(
            self.camera,
            self.stage,
            coarse,
            fine,
            None,
            objective,
        )
        self.focus_thread = t
        t.finished.connect(self.magic_focus_finished)
        return t

    def magic_focus_finished(self):
        """Called when focus search thread has finished."""
        if self.focus_thread is None:
            return
        print("Focus search finished")
        print(f"{self.focus_thread.best_z=}")
        print(f"{self.focus_thread.best_positions=}")
        print(f"{self.focus_thread.tab_coarse=}")
        print(f"{self.focus_thread.tab_fine=}")

    @property
    def settings(self) -> dict:
        """Export settings to a dict for yaml serialization."""
        settings = super().settings
        points = self.autofocus_helper.registered_points
        if len(points) == 3:
            settings["autofocus_points"] = [
                list(p) for p in self.autofocus_helper.registered_points
            ]
        return settings

    @settings.setter
    def settings(self, data: dict):
        """Import settings from a dict."""
        Instrument.settings.__set__(self, data)
        points = data.get("autofocus_points", [])
        if len(points) == 3:
            self.autofocus_helper.clear()
            for point in points:
                if type(point) is list and len(point) == 3:
                    self.autofocus_helper.register(point[0], point[1], point[2])
            self.parameter_changed.emit(
                "autofocus_points", self.autofocus_helper.registered_points
            )
