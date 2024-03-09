from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QToolBar, QPushButton
from ...utils.util import colored_image, resource_path

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class ZoomToolbar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio"):
        super().__init__("Zoom control", laser_studio)
        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
        )
        self.setFloatable(True)

        # Zoom in (*2).
        w = QPushButton(self)
        w.setToolTip("Zoom in")
        w.setIcon(
            QIcon(
                colored_image(
                    ":/icons/fontawesome-free/magnifying-glass-plus-solid.svg"
                )
            )
        )
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(
            lambda: laser_studio.viewer.__setattr__(
                "zoom", laser_studio.viewer.zoom * 2.0
            )
        )
        self.addWidget(w)

        # Zoom out (/2).
        w = QPushButton(self)
        w.setToolTip("Zoom out")
        w.setIcon(
            QIcon(
                colored_image(
                    ":/icons/fontawesome-free/magnifying-glass-minus-solid.svg"
                )
            )
        )
        w.setIconSize(QSize(24, 24))
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
            QIcon(colored_image(":/icons/fontawesome-free/arrows-to-dot-solid.svg"))
        )
        w.setIconSize(QSize(24, 24))
        w.toggled.connect(laser_studio.viewer.follow_stage_sight)
        w.setChecked(True)
        self.addWidget(w)
