from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QToolBar,
    QPushButton,
)
from ...util import resource_path

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


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
