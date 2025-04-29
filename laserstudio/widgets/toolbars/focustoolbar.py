from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPainter
from PyQt6.QtWidgets import QToolBar, QPushButton, QLabel, QMessageBox
import numpy
from pystages import Vector
from ...utils.util import colored_image
from ..coloredbutton import ColoredPushButton
from ...instruments.camera import CameraInstrument
from ...instruments.stage import StageInstrument
from ...instruments.focus import FocusInstrument
from PyQt6.QtCharts import QLineSeries, QChart, QChartView


class FocusToolBar(QToolBar):
    """ToolBar for focus registration and autofocus."""

    def __init__(
        self,
        stage: StageInstrument,
        camera: CameraInstrument,
        focus_helper: FocusInstrument,
    ):
        """
        :param autofocus_helper: Stores the registered points and calculates focus on demand.
        """
        super().__init__("Focus")
        self.setObjectName("toolbar-focus")  # For settings save and restore
        self.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.setFloatable(True)

        self.focus_helper: FocusInstrument = focus_helper
        self.stage = stage
        self.camera = camera

        # Try to find focus automatically
        self.button_magic_focus = w = ColoredPushButton(
            ":/icons/fontawesome-free/wand-magic-sparkles-solid.svg", parent=self
        )
        w.setCheckable(True)
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

        # Show current sharpness value
        self.sharpness = QLabel("")
        self.sharpness.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sharpness.setStyleSheet("padding-left: 10px;padding-right: 10px")
        self.camera.new_image.connect(
            lambda: self.sharpness.setText(f"{self.camera.laplacian_std_dev:.2f}")
        )
        self.sharpness.setToolTip("The sharpness value of the current image.")
        self.addWidget(self.sharpness)

    def magic_focus(self):
        """
        Estimates automatically the correct focus by moving the stage and analysing the
        resulting camera image. This is executed in a thread.
        """
        assert (
            self.focus_helper.focus_thread is None
            or not self.focus_helper.focus_thread.isRunning()
        ), "Magic Focus thread is already running"
        self.button_magic_focus.setEnabled(False)
        t = self.focus_helper.magic_focus()
        t.finished.connect(self.magic_focus_finished)

    def magic_focus_finished(self):
        """Called when focus search thread has finished."""
        # Reenable the button
        self.button_magic_focus.setChecked(False)
        self.button_magic_focus.setEnabled(True)

        # Show the graphs
        assert (t := self.focus_helper.focus_thread) is not None
        if (tab := t.tab_coarse) is not None:
            self.cv = w = QChartView()
            w.setChart(c := QChart())
            w.setRenderHint(QPainter.RenderHint.Antialiasing)
            w.setMinimumSize(600, 400)
            s = QLineSeries()
            s.setName("Coarse")
            for z, sharpness in tab:
                s.append(z, sharpness)
            c.addSeries(s)

            if (tab := t.tab_fine) is not None:
                s = QLineSeries()
                s.setName("Fine")
                for z, sharpness in tab:
                    s.append(z, sharpness)
                c.addSeries(s)
            c.createDefaultAxes()
            w.show()

    def register(self):
        """
        Registers a new focus point. If three focus points are already defined, the
        farther point is replaced.
        """
        pos = self.stage.position
        if len(self.focus_helper.autofocus_helper) == 3:
            dists = [
                numpy.linalg.norm((Vector(*p).xy - pos.xy).data)
                for p in self.focus_helper.autofocus_helper.registered_points
            ]
            del self.focus_helper.autofocus_helper.registered_points[
                dists.index(min(dists))
            ]
        self.focus_helper.register((pos.x, pos.y, pos.z))

    def autofocus(self):
        """
        Calculate focus for the given position and apply it, if possible.
        """
        if len(self.focus_helper.autofocus_helper) < 3:
            # Prompt a dialog
            QMessageBox.critical(
                self,
                "Focus",
                f"Not enough points registered for autofocus ({len(self.focus_helper.autofocus_helper)} over 3 required).",
            )
            return

        try:
            self.focus_helper.autofocus()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Focus",
                str(e),
            )
            return
