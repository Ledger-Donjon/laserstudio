from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QToolBar,
    QPushButton,
)
from ...utils.util import colored_image
from ..coloredbutton import ColoredPushButton
from ...widgets.return_line_edit import ReturnSpinBox

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class ScanToolbar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio"):
        super().__init__("Scanning Zones", laser_studio)
        self.setObjectName("toolbar-scanning")  # For settings save and restore
        group = laser_studio.viewer_buttons_group
        self.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.setFloatable(True)

        # Activate scan-zone definition mode
        w = ColoredPushButton(":/icons/region.svg", parent=self)
        w.setToolTip("Define scanning regions. Hold Shift key to remove zone.")
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

        # Scanning enable/disable button
        w = ColoredPushButton(":/icons/no-scan.svg", ":/icons/scan.svg", parent=self)
        w.setToolTip("Enable/Disable scanning")
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        w.setChecked(laser_studio.scanning_enabled)
        w.toggled.connect(lambda v: laser_studio.__setattr__("scanning_enabled", v))
        self.addWidget(w)

        # Density
        w = self.density = ReturnSpinBox()
        w.setToolTip(
            "Scan density. The bigger it is, the smaller average distance between consecutive points is."
        )
        w.setMinimum(1)
        w.setMaximum(1000)
        w.setValue(laser_studio.viewer.scan_geometry.scan_path_generator.density)
        w.returnPressed.connect(
            lambda: laser_studio.viewer.scan_geometry.__setattr__(
                "density", self.density.value()
            )
        )
        w.reset()
        self.addWidget(w)
