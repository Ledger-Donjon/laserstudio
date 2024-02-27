from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QToolBar, QPushButton
from ...util import resource_path
from ..stagesight import StageSightViewer, StageSight
from ..camerawizard import CameraWizard

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
            QPixmap(resource_path(":/icons/fontawesome-free/video-solid-24.png")),
            QIcon.Mode.Normal,
            QIcon.State.On,
        )
        icon.addPixmap(
            QPixmap(resource_path(":/icons/fontawesome-free/video-slash-solid-24.png")),
            QIcon.Mode.Normal,
            QIcon.State.Off,
        )
        w.setIcon(icon)
        w.setIconSize(QSize(24, 24))
        w.toggled.connect(
            lambda b: laser_studio.viewer.stage_sight.__setattr__("show_image", b)
        )
        self.addWidget(w)

        laser_studio.camera_wizard = CameraWizard(
            laser_studio.instruments, laser_studio, laser_studio
        )
        w = QPushButton(self)
        w.setText("Distortion Wizard")
        w.clicked.connect(
            lambda: (
                laser_studio.camera_wizard.show()
                if laser_studio.camera_wizard is not None
                else ()
            )
        )
        self.addWidget(w)

        # Second representation of the camera image
        stage_sight = StageSight(None, self.camera)
        w = StageSightViewer(stage_sight)
        w.setHidden(True)
        self.addWidget(w)
