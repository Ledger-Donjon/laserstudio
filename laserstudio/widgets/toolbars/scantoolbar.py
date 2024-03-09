from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QIntValidator
from PyQt6.QtWidgets import (
    QToolBar,
    QPushButton,
)
from ...utils.util import resource_path, colored_image
from ...widgets.return_line_edit import ReturnLineEdit

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
        w.setToolTip("Define scanning regions. Hold Shift key to remove zone.")
        w.setIcon(QIcon(resource_path(":/icons/icons8/region.png")))
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        group.addButton(w)
        group.setId(w, laser_studio.viewer.Mode.ZONE)
        self.addWidget(w)

        # Go-to-next position button
        w = QPushButton(self)
        w.setToolTip("Go to next Scan Point")
        w.setIcon(
            QIcon(colored_image(":/icons/fontawesome-free/forward-step-solid.svg"))
        )
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(laser_studio.handle_go_next)
        self.addWidget(w)

        # Density
        w = self.density = ReturnLineEdit()
        w.setToolTip(
            "Scan density. The bigger it is, the smaller average distance between consecutive points is."
        )
        w.setText(str(laser_studio.viewer.scan_geometry.scan_path_generator.density))
        w.setValidator(QIntValidator(1, 1000))
        w.returnPressed.connect(
            lambda: laser_studio.viewer.scan_geometry.__setattr__(
                "density", int(self.density.text())
            )
        )
        self.addWidget(w)
