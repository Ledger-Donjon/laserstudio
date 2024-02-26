from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QToolBar,
    QPushButton,
    QLabel,
)
from ..util import resource_path
from .keyboardbox import KeyboardBox
from .stagesight import StageSightViewer, StageSight
from .camerawizard import CameraWizard


if TYPE_CHECKING:
    from ..laserstudio import LaserStudio


def main_toolbar(laser_studio: "LaserStudio") -> QToolBar:
    group = laser_studio.viewer_buttons_group
    toolbar = QToolBar(laser_studio)
    toolbar.setWindowTitle("Main")
    toolbar.setAllowedAreas(
        Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
    )
    toolbar.setFloatable(True)

    # Icon Logo
    w = QLabel()
    w.setPixmap(
        QPixmap(resource_path(":/icons/logo.png")).scaled(
            64, 64, transformMode=Qt.TransformationMode.SmoothTransformation
        )
    )
    w.setAlignment(Qt.AlignmentFlag.AlignCenter)
    toolbar.addWidget(w)

    # Button to unselect any viewer mode.
    w = QPushButton(toolbar)
    w.setToolTip("Cancel any mode")
    w.setIcon(QIcon(resource_path(":/icons/icons8/cursor.png")))
    w.setIconSize(QSize(24, 24))
    w.setCheckable(True)
    w.setChecked(True)
    toolbar.addWidget(w)
    group.addButton(w)
    group.setId(w, laser_studio.viewer.Mode.NONE)
    return toolbar


def picture_toolbar(laser_studio: "LaserStudio") -> QToolBar:
    group = laser_studio.viewer_buttons_group
    # Toolbar: Background picture
    toolbar = QToolBar(laser_studio)
    toolbar.setWindowTitle("Background picture")
    toolbar.setAllowedAreas(
        Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
    )
    toolbar.setFloatable(True)

    # Button to select Pining mode.
    w = QPushButton(toolbar)
    w.setToolTip("Pin mode")
    w.setIcon(QIcon(resource_path(":/icons/icons8/pin.png")))
    w.setIconSize(QSize(24, 24))
    w.setCheckable(True)
    toolbar.addWidget(w)
    group.addButton(w)
    group.setId(w, laser_studio.viewer.Mode.PIN)

    # Button to load background picture.
    w = QPushButton(toolbar)
    w.setToolTip("Load background picture from file")
    w.setIcon(QIcon(resource_path(":/icons/icons8/picture.png")))
    w.setIconSize(QSize(24, 24))
    w.clicked.connect(laser_studio.viewer.load_picture)
    toolbar.addWidget(w)
    return toolbar


def zoom_toolbar(laser_studio: "LaserStudio") -> QToolBar:
    toolbar = QToolBar(laser_studio)
    toolbar.setWindowTitle("Zoom control")
    toolbar.setAllowedAreas(
        Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
    )
    toolbar.setFloatable(True)

    # Zoom in (*2).
    w = QPushButton(toolbar)
    w.setText("Z+")
    w.setToolTip("Zoom in")
    w.clicked.connect(
        lambda: laser_studio.viewer.__setattr__("zoom", laser_studio.viewer.zoom * 2.0)
    )
    toolbar.addWidget(w)

    # Zoom out (/2).
    w = QPushButton(toolbar)
    w.setText("Z-")
    w.setToolTip("Zoom out")
    w.clicked.connect(
        lambda: laser_studio.viewer.__setattr__("zoom", laser_studio.viewer.zoom * 0.5)
    )
    toolbar.addWidget(w)

    # Zoom reset (1:1).
    w = QPushButton(toolbar)
    w.setText("Z:1x")
    w.setToolTip("Reset zoom")
    w.clicked.connect(lambda: laser_studio.viewer.__delattr__("zoom"))
    toolbar.addWidget(w)

    # Zoom to all.
    w = QPushButton(toolbar)
    w.setToolTip("Reset Viewer to see all elements")
    w.setIcon(QIcon(resource_path(":/icons/icons8/zoom-reset.png")))
    w.setIconSize(QSize(24, 24))
    w.clicked.connect(laser_studio.viewer.reset_camera)
    toolbar.addWidget(w)

    # Button to enable/disable StageSight position tracking.
    w = QPushButton(toolbar)
    w.setToolTip("Follow stage")
    w.setCheckable(True)
    w.setIcon(
        QIcon(resource_path(":/icons/fontawesome-free/arrows-to-dot-solid-24.png"))
    )
    w.setIconSize(QSize(24, 24))
    w.toggled.connect(laser_studio.viewer.follow_stagesight)
    w.setChecked(True)
    toolbar.addWidget(w)
    return toolbar


def stage_toolbar(laser_studio: "LaserStudio") -> QToolBar:
    assert laser_studio.instruments.stage is not None
    group = laser_studio.viewer_buttons_group
    toolbar = QToolBar(laser_studio)
    toolbar.setWindowTitle("Stage control")
    toolbar.setAllowedAreas(
        Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
    )
    toolbar.setFloatable(True)

    # Activate stage-move mode
    w = QPushButton(toolbar)
    w.setToolTip("Move stage mode")
    w.setIcon(QIcon(resource_path(":/icons/fontawesome-free/directions-solid-24.png")))
    w.setIconSize(QSize(24, 24))
    w.setCheckable(True)
    toolbar.addWidget(w)
    group.addButton(w)
    group.setId(w, laser_studio.viewer.Mode.STAGE)

    # Keyboard box
    w = KeyboardBox(laser_studio.instruments.stage)
    toolbar.addWidget(w)
    return toolbar


def scan_toolbar(laser_studio: "LaserStudio") -> QToolBar:
    group = laser_studio.viewer_buttons_group
    toolbar = QToolBar(laser_studio)
    toolbar.setWindowTitle("Scanning Zones")
    toolbar.setAllowedAreas(
        Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
    )
    toolbar.setFloatable(True)

    # Activate scan-zone definition mode
    w = QPushButton(toolbar)
    w.setToolTip("Define scanning regions")
    w.setIcon(QIcon(resource_path(":/icons/icons8/region.png")))
    w.setIconSize(QSize(24, 24))
    w.setCheckable(True)
    group.addButton(w)
    group.setId(w, laser_studio.viewer.Mode.ZONE)
    toolbar.addWidget(w)

    # Go-to-next position button
    w = QPushButton(toolbar)
    w.setToolTip("Go Next Scan Point")
    w.setIcon(
        QIcon(resource_path(":/icons/fontawesome-free/forward-step-solid-24.png"))
    )
    w.setIconSize(QSize(24, 24))
    w.clicked.connect(laser_studio.handle_go_next)
    toolbar.addWidget(w)

    return toolbar


def camera_toolbar(laser_studio: "LaserStudio") -> QToolBar:
    assert laser_studio.instruments.camera is not None
    toolbar = QToolBar(laser_studio)
    toolbar.setWindowTitle("Camera parameters")
    toolbar.setAllowedAreas(
        Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
    )
    toolbar.setFloatable(True)

    # Button to toggle off or on the camera image presentation in main viewer
    w = QPushButton(toolbar)
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
    toolbar.addWidget(w)

    laser_studio.camera_wizard = CameraWizard(
        laser_studio.instruments, laser_studio, laser_studio
    )
    w = QPushButton(toolbar)
    w.setText("Distortion Wizard")
    w.clicked.connect(
        lambda: (
            laser_studio.camera_wizard.show()
            if laser_studio.camera_wizard is not None
            else ()
        )
    )
    toolbar.addWidget(w)

    # Second representation of the camera image
    stage_sight = StageSight(None, laser_studio.instruments.camera)
    w = StageSightViewer(stage_sight)
    w.setHidden(True)
    toolbar.addWidget(w)
    return toolbar
