from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QToolBar, QPushButton, QLabel, QMenu
from ...utils.util import resource_path, colored_image

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

        w.setIcon(
            QIcon(
                colored_image(
                    ":/icons/fontawesome-free/arrow-pointer-solid.svg",
                )
            )
        )

        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        w.setChecked(True)
        self.addWidget(w)
        group.addButton(w)
        group.setId(w, laser_studio.viewer.Mode.NONE)

        w = QPushButton(self)
        w.setToolTip("Settings")
        w.setIcon(QIcon(colored_image(":/icons/fontawesome-free/sliders-solid.svg")))
        w.setIconSize(QSize(24, 24))
        settings_menu = QMenu("Settings", self)
        settings_menu.addAction("Save settings", laser_studio.save_settings)
        settings_menu.addAction("Load settings", laser_studio.reload_settings)
        w.setMenu(settings_menu)
        self.addWidget(w)
