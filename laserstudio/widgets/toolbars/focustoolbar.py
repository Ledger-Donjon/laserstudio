from time import sleep
from PyQt6.QtCore import Qt, QSize, QThread
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QToolBar, QPushButton
import numpy as np
import scipy.signal
from pystages import Autofocus, Vector
from laserstudio.instruments.camera_nit import CameraNITInstrument
from laserstudio.utils.util import colored_image
from typing import Optional


class FocusToolbar(QToolBar):
    """Toolbar for focus registration and autofocus."""

    def __init__(self, stage, camera: CameraNITInstrument, autofocus_helper: Autofocus):
        """
        :param autofocus_helper: Stores the registered points and calculates focus on demand.
        """
        super().__init__("Focus")
        self.setObjectName("toolbar-focus")  # For settings save and restore
        self.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.setFloatable(True)

        # Set when a focus search is running, then cleared.
        # This is used to prevent launching two search threads at the same time.
        self.focus_thread: Optional[FocusThread] = None

        self.autofocus_helper = autofocus_helper
        self.stage = stage
        self.camera = camera

        # Try to find focus automatically
        self.button_magic_focus = w = QPushButton(self)
        w.setIcon(
            QIcon(
                colored_image(":/icons/fontawesome-free/wand-magic-sparkles-solid.svg")
            )
        )
        w.setIconSize(QSize(24, 24))
        w.setToolTip(
            "Automatically find best focus position using camera image analysis."
        )
        w.clicked.connect(self.magic_focus)
        self.addWidget(w)

        # Set focus point at current position
        w = QPushButton(self)
        w.setIcon(QIcon(colored_image(":/icons/fontawesome-free/wrench-solid.svg")))
        w.setIconSize(QSize(24, 24))
        w.setToolTip("Register current position for focusing.")
        w.clicked.connect(self.register)
        self.addWidget(w)

        # Autofocus
        w = QPushButton(self)
        w.setIcon(QIcon(colored_image(":/icons/fontawesome-free/glasses-solid.svg")))
        w.setIconSize(QSize(24, 24))
        w.setToolTip("Automatically focus based on 3 registered positions.")
        w.clicked.connect(self.autofocus)
        self.addWidget(w)

    def magic_focus(self):
        """
        Estimates automatically the correct focus by moving the stage and analysing the
        resulting camera image. This is executed in a thread.
        """
        assert self.focus_thread is None
        self.button_magic_focus.setEnabled(False)
        # Adapt range depending on currently selected microscope objective.
        objective = self.camera.objective
        t = FocusThread(
            self.camera,
            self.stage,
            FocusSearchSettings(4000 / objective, 50, 4, False),
            FocusSearchSettings(200 / objective, 20, 16, False),
            None,
        )
        self.focus_thread = t
        t.finished.connect(self.magic_focus_finished)
        t.start()

    def magic_focus_finished(self):
        """Called when focus search thread has finished."""
        assert self.focus_thread is not None
        self.focus_thread = None
        self.button_magic_focus.setEnabled(True)

    def register(self):
        """
        Registers a new focus point. If three focus points are already defined, the
        farther point is replaced.
        """
        pos = self.stage.position
        if len(self.autofocus_helper) == 3:
            dists = [
                np.linalg.norm((Vector(*p).xy - pos.xy).data)
                for p in self.autofocus_helper.registered_points
            ]
            del self.autofocus_helper.registered_points[dists.index(min(dists))]
        self.autofocus_helper.register(pos.x, pos.y, pos.z)

    def autofocus(self):
        """
        Calculate focus for the given position and apply it, if possible.
        """
        pos = self.stage.position
        z = self.autofocus_helper.focus(pos.x, pos.y)
        if abs(z - pos.z < 250):
            print("DIFF", z, pos.z)
            self.stage.position = Vector(pos.x, pos.y, z)
        else:
            print("Warning: too big Z difference")


class FocusSearchSettings:
    """Parameters for the focus search procedure."""

    def __init__(self, span: float, steps: int, avg: int, multi_peaks: bool):
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
        """
        assert span > 0
        assert span < 1000  # In case of bug, prevent large span
        assert steps >= 2
        assert avg >= 1
        self.span = span
        self.steps = steps
        self.avg = avg
        self.multi_peaks = multi_peaks


class FocusThread(QThread):
    """
    Thread to perform best focus position research by moving a stage and analysing the
    images of a camera.
    """

    def __init__(
        self,
        camera: CameraNITInstrument,
        stage,
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
        self.__camera.averaging = settings.avg
        best_z = None
        best_std_dev = None
        tab = []
        pos: Vector = Vector()
        for i in range(settings.steps):
            z = (z_step * i) + z_min
            pos = stage.position
            stage.move_to(Vector(pos.x, pos.y, z), wait=True)
            self.__camera.averaging_restart()
            self.__camera.reset_counter()
            # +3: pynit does some pipelining in the image processing, there can
            # be latency in the images. This is a bit hacky.
            while self.__camera.counter < settings.avg + 3:
                sleep(0.05)
            std_dev = self.__camera.laplacian_std_dev
            tab.append((z, std_dev))
            if (best_std_dev is None) or (std_dev > best_std_dev):
                best_std_dev = std_dev
                best_z = z

        tab = np.array(tab)
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
            best_z = peaks[-1][0]

        stage.move_to(Vector(pos.x, pos.y, best_z), wait=True)
        return (best_z, tab, peaks)

    def run(self):
        """
        Perform focus research, with first coarse settings, and then eventually with fine
        settings.
        """
        avg_prev = self.__camera.averaging
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

        self.__camera.averaging = avg_prev  # Restore setting
