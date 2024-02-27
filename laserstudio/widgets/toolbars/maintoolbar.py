from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QToolBar, QPushButton, QLabel
from ...util import resource_path

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
