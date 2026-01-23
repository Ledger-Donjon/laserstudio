from typing import TYPE_CHECKING
import logging
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QToolBar, QPushButton, QLabel, QMenu
from ...utils.util import resource_path, colored_image, save_configuration_file
from ..coloredbutton import ColoredPushButton

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class MainToolBar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio"):
        """
        :param viewer: Required for the menu to remove markers.
        """
        super().__init__("Main", laser_studio)
        self.laser_studio = laser_studio
        self.setObjectName("toolbar-main")  # For settings save and restore
        group = laser_studio.viewer_buttons_group
        self.setAllowedAreas(Qt.ToolBarArea.AllToolBarAreas)
        self.setFloatable(True)

        # Icon Logo
        w = QLabel()
        w.setPixmap(
            QPixmap(resource_path(":/icons/logo.svg")).scaled(
                32, 32, transformMode=Qt.TransformationMode.SmoothTransformation
            )
        )
        w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.addWidget(w)

        # Button to unselect any viewer mode.
        w = ColoredPushButton(":/icons/arrow-pointer-solid.svg", parent=self)
        w.setToolTip("Cancel any mode")
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
        settings_menu.addAction(
            "Save configuration file",
            lambda: save_configuration_file(laser_studio.config),
        )
        self.log_level_menu = QMenu("Log level", self)

        def set_log_level(level: int) -> None:
            self.laser_studio.set_log_level(level)
            for action in self.log_level_menu.actions():
                action.setChecked(action.text() == logging.getLevelName(level))

        for level in [
            logging.DEBUG,
            logging.INFO,
            logging.WARNING,
            logging.ERROR,
            logging.CRITICAL,
        ]:
            action = self.log_level_menu.addAction(
                logging.getLevelName(level), lambda _level=level: set_log_level(_level)
            )
            action.setCheckable(True) if action is not None else None
        set_log_level(logging.getLogger("laserstudio").level)
        settings_menu.addMenu(self.log_level_menu)
        w.setMenu(settings_menu)
        self.addWidget(w)
