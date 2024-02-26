from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QToolBar,
    QPushButton,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from ...util import resource_path
from ..keyboardbox import KeyboardBox
from ..stagesight import StageSightViewer, StageSight
from ..camerawizard import CameraWizard

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class MainToolbar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio"):
        super().__init__("Main", laser_studio)
        group = laser_studio.viewer_buttons_group
        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
        )
        self.setFloatable(True)

        # Icon Logo
        w = QLabel()
        w.setPixmap(
            QPixmap(resource_path(":/icons/logo.png")).scaled(
                64, 64, transformMode=Qt.TransformationMode.SmoothTransformation
            )
        )
        w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.addWidget(w)

        # Button to unselect any viewer mode.
        w = QPushButton(self)
        w.setToolTip("Cancel any mode")
        w.setIcon(QIcon(resource_path(":/icons/icons8/cursor.png")))
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        w.setChecked(True)
        self.addWidget(w)
        group.addButton(w)
        group.setId(w, laser_studio.viewer.Mode.NONE)

        w = QPushButton(self)
        w.setText("Save")
        w.setToolTip("Save settings to settings.yaml")
        w.clicked.connect(laser_studio.save_settings)
        self.addWidget(w)
        w = QPushButton(self)
        w.setText("Restore")
        w.setToolTip("Restore settings from settings.yaml")
        w.clicked.connect(laser_studio.reload_settings)
        self.addWidget(w)


class PictureToolbar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio"):
        super().__init__("Background picture", laser_studio)
        group = laser_studio.viewer_buttons_group
        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
        )
        self.setFloatable(True)

        # Button to select Pining mode.
        w = QPushButton(self)
        w.setToolTip("Pin mode")
        w.setIcon(QIcon(resource_path(":/icons/icons8/pin.png")))
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        self.addWidget(w)
        group.addButton(w)
        group.setId(w, laser_studio.viewer.Mode.PIN)

        # Button to load background picture.
        w = QPushButton(self)
        w.setToolTip("Load background picture from file")
        w.setIcon(QIcon(resource_path(":/icons/icons8/picture.png")))
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(laser_studio.viewer.load_picture)
        self.addWidget(w)


class ZoomToolbar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio"):
        super().__init__("Zoom control", laser_studio)
        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
        )
        self.setFloatable(True)

        # Zoom in (*2).
        w = QPushButton(self)
        w.setText("Z+")
        w.setToolTip("Zoom in")
        w.clicked.connect(
            lambda: laser_studio.viewer.__setattr__(
                "zoom", laser_studio.viewer.zoom * 2.0
            )
        )
        self.addWidget(w)

        # Zoom out (/2).
        w = QPushButton(self)
        w.setText("Z-")
        w.setToolTip("Zoom out")
        w.clicked.connect(
            lambda: laser_studio.viewer.__setattr__(
                "zoom", laser_studio.viewer.zoom * 0.5
            )
        )
        self.addWidget(w)

        # Zoom reset (1:1).
        w = QPushButton(self)
        w.setText("Z:1x")
        w.setToolTip("Reset zoom")
        w.clicked.connect(lambda: laser_studio.viewer.__delattr__("zoom"))
        self.addWidget(w)

        # Zoom to all.
        w = QPushButton(self)
        w.setToolTip("Reset Viewer to see all elements")
        w.setIcon(QIcon(resource_path(":/icons/icons8/zoom-reset.png")))
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(laser_studio.viewer.reset_camera)
        self.addWidget(w)

        # Button to enable/disable StageSight position tracking.
        w = QPushButton(self)
        w.setToolTip("Follow stage")
        w.setCheckable(True)
        w.setIcon(
            QIcon(resource_path(":/icons/fontawesome-free/arrows-to-dot-solid-24.png"))
        )
        w.setIconSize(QSize(24, 24))
        w.toggled.connect(laser_studio.viewer.follow_stagesight)
        w.setChecked(True)
        self.addWidget(w)


class StageToolbar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio"):
        assert laser_studio.instruments.stage is not None
        self.stage = laser_studio.instruments.stage
        super().__init__("Stage control", laser_studio)
        group = laser_studio.viewer_buttons_group
        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
        )
        self.setFloatable(True)

        # Activate stage-move mode
        w = QPushButton(self)
        w.setToolTip("Move stage mode")
        w.setIcon(
            QIcon(resource_path(":/icons/fontawesome-free/directions-solid-24.png"))
        )
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        self.addWidget(w)
        group.addButton(w)
        group.setId(w, laser_studio.viewer.Mode.STAGE)

        w1 = QWidget(self)
        vbox = QVBoxLayout(w1)
        w1.setLayout(vbox)
        for i in range(len(self.stage.mem_points)):
            w = QPushButton(self)
            w.setText(f"Go to M{i}")
            w.setToolTip(f"{self.stage.mem_points[i].data}")
            w.clicked.connect(
                lambda _i=i: self.stage.move_to(self.stage.mem_points[_i], wait=True)
            )
            vbox.addWidget(w)
        self.addWidget(w1)

        w = QPushButton(self)
        w.setText("Home")
        w.clicked.connect(self.stage.stage.home)
        self.addWidget(w)

        # Keyboard box
        w = KeyboardBox(self.stage)
        self.addWidget(w)


class ScanToolbar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio"):
        super().__init__("Scanning Zones", laser_studio)
        group = laser_studio.viewer_buttons_group
        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
        )
        self.setFloatable(True)

        # Activate scan-zone definition mode
        w = QPushButton(self)
        w.setToolTip("Define scanning regions")
        w.setIcon(QIcon(resource_path(":/icons/icons8/region.png")))
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        group.addButton(w)
        group.setId(w, laser_studio.viewer.Mode.ZONE)
        self.addWidget(w)

        # Go-to-next position button
        w = QPushButton(self)
        w.setToolTip("Go Next Scan Point")
        w.setIcon(
            QIcon(resource_path(":/icons/fontawesome-free/forward-step-solid-24.png"))
        )
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(laser_studio.handle_go_next)
        self.addWidget(w)


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
