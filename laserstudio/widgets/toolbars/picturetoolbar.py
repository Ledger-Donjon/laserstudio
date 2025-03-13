from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QToolBar,
    QPushButton,
)
from ...utils.util import colored_image
from ..coloredbutton import ColoredPushButton

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class PictureToolbar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio"):
        super().__init__("Background picture", laser_studio)
        self.setObjectName(
            "toolbar-background-picture"
        )  # For settings save and restore
        group = laser_studio.viewer_buttons_group
        self.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.setFloatable(True)

        # Button to select Pining mode.
        w = ColoredPushButton(":/icons/pin.svg", parent=self)
        w.setToolTip("Pin mode")
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
        w.clicked.connect(lambda: laser_studio.viewer.load_picture())
        self.addWidget(w)

        # Button to clear background picture.
        w = QPushButton(self)
        w.setToolTip("Clear background picture")
        w.setIcon(QIcon(colored_image(":/icons/fontawesome-free/image-regular.svg")))
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(lambda: laser_studio.viewer.clear_picture())
        self.addWidget(w)

        # Button to select set current image as background.
        w = QPushButton(self)
        w.setToolTip("Set current image as background")
        w.setIcon(QIcon(colored_image(":/icons/fontawesome-free/image-regular.svg")))
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(lambda: laser_studio.viewer.snap_picture_from_camera())
        self.addWidget(w)
