from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QToolBar, QPushButton, QLabel
import numpy
from pystages import Autofocus, Vector
from ...utils.util import colored_image
from ..coloredbutton import ColoredPushButton
from ...instruments.camera import CameraInstrument
from ...instruments.stage import StageInstrument
from ...instruments.focus import FocusThread
from typing import Optional


class FocusToolbar(QToolBar):
    """Toolbar for focus registration and autofocus."""

    def __init__(
        self,
        stage: StageInstrument,
        camera: CameraInstrument,
        autofocus_helper: Autofocus,
    ):
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
        assert self.camera.focus_thread is None
        self.button_magic_focus.setEnabled(False)
        t = self.camera.magic_focus(self.stage)
        t.finished.connect(self.magic_focus_finished)
        t.start()

    def magic_focus_finished(self):
        """Called when focus search thread has finished."""
        self.button_magic_focus.setChecked(False)
        self.button_magic_focus.setEnabled(True)

    def register(self):
        """
        Registers a new focus point. If three focus points are already defined, the
        farther point is replaced.
        """
        pos = self.stage.position
        if len(self.autofocus_helper) == 3:
            dists = [
                numpy.linalg.norm((Vector(*p).xy - pos.xy).data)
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
