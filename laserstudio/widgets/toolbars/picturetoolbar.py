from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QToolBar,
    QPushButton,
)
from ...utils.util import resource_path, colored_image

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


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
        w.setIcon(QIcon(colored_image(":/icons/fontawesome-free/image-regular.svg")))
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(laser_studio.viewer.load_picture)
        self.addWidget(w)
