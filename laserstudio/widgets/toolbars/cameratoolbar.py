from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QToolBar, QPushButton
from ...utils.util import resource_path
from ..stagesight import StageSightViewer, StageSight
from ..camerawizards import CameraDistortionWizard, ProbesPositionWizard

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class CameraToolbar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio"):
        assert laser_studio.instruments.camera is not None
        self.camera = laser_studio.instruments.camera
        super().__init__("Camera parameters", laser_studio)
        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
        )
        self.setFloatable(True)

        # Button to toggle off or on the camera image presentation in main viewer
        w = QPushButton(self)
        w.setToolTip("Show/Hide Image")
        w.setCheckable(True)
        w.setChecked(True)
        icon = QIcon()
        icon.addPixmap(
            QPixmap(resource_path(":/icons/fontawesome-free/video-solid.svg")),
            QIcon.Mode.Normal,
            QIcon.State.On,
        )
        icon.addPixmap(
            QPixmap(resource_path(":/icons/fontawesome-free/video-slash-solid.svg")),
            QIcon.Mode.Normal,
            QIcon.State.Off,
        )
        w.setIcon(icon)
        w.setIconSize(QSize(24, 24))
        w.toggled.connect(
            lambda b: laser_studio.viewer.stage_sight.__setattr__("show_image", b)
        )
        self.addWidget(w)

        w = QPushButton(self)
        w.setText("Distortion Wizard")
        self.camera_distortion_wizard = CameraDistortionWizard(laser_studio, self)
        w.clicked.connect(lambda: self.camera_distortion_wizard.show())
        self.addWidget(w)

        self.probes_distortion_wizard = ProbesPositionWizard(laser_studio, self)
        w = QPushButton(self)
        w.setText("Probes/Spots Position Wizard")
        w.clicked.connect(lambda: (self.probes_distortion_wizard.show()))
        self.addWidget(w)
        w.setHidden(
            len(laser_studio.instruments.probes) + len(laser_studio.instruments.lasers)
            == 0
        )

        # Second representation of the camera image
        stage_sight = StageSight(None, self.camera)
        w = StageSightViewer(stage_sight)
        w.setHidden(True)
        self.addWidget(w)
