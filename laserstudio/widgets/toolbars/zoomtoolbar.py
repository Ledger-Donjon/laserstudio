from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QToolBar, QPushButton
from ...utils.util import colored_image, resource_path
from ..coloredbutton import ColoredPushButton

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class ZoomToolbar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio"):
        super().__init__("Zoom control", laser_studio)
        self.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
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
        w.setToolTip("Reset zoom")
        w.setIcon(QIcon(colored_image(":/icons/magnifying-glass-one-solid.svg")))
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(lambda: laser_studio.viewer.__delattr__("zoom"))
        self.addWidget(w)

        # Zoom to all.
        w = QPushButton(self)
        w.setToolTip("Reset Viewer to see all elements")
        w.setIcon(QIcon(colored_image(":/icons/magnifying-glass-all-solid.svg")))
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(laser_studio.viewer.reset_camera)
        self.addWidget(w)

        # Button to enable/disable StageSight position tracking.
        w = ColoredPushButton(
            icon_path=":/icons/fontawesome-free/arrows-to-dot-solid.svg", parent=self
        )
        w.setToolTip("Center on focused item")
        w.setCheckable(True)
        w.setIconSize(QSize(24, 24))
        w.toggled.connect(laser_studio.viewer.follow_stage_sight)
        w.setChecked(True)
        self.addWidget(w)

        # Position
        self.position = QPushButton("Position")
        self.position.setCheckable(True)
        self.position.toggled.connect(self.activate_mouse_tracking)
        self.position_signal = laser_studio.viewer.mouse_moved
        self.addWidget(self.position)
        self.position.setChecked(True)

    def activate_mouse_tracking(self, activate: bool):
        if not activate:
            self.position.setText("Position")
            self.position_signal.disconnect(self.update_position)
        else:
            self.position_signal.connect(self.update_position)

    def update_position(self, x: float, y: float):
        self.position.setText(f"{x:.02f}µm {y:.02f}µm")
