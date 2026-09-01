from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QColorConstants
from PyQt6.QtWidgets import QToolBar, QPushButton, QSizePolicy, QComboBox
from ...utils.util import colored_image
from ..coloredbutton import ColoredPushButton
from ...widgets.return_line_edit import ReturnSpinBox, ReturnDoubleSpinBox
from ...utils.colors import LedgerColors
from ...utils.util import create_color_qicon
from ...utils.scanzones import ScanZone

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class ScanToolBar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio"):
        super().__init__("Scanning Zones", laser_studio)
        self.setObjectName("toolbar-scanning")  # For settings save and restore
        group = laser_studio.viewer_buttons_group
        self.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.setFloatable(True)
        # Guards __on_zone_selected against currentIndexChanged firing while
        # __sync_zones is itself rebuilding the combo box (see __sync_zones).
        self.__syncing = False

        # Activate scan-zone definition modes
        w = ColoredPushButton(":/icons/region_rect.svg", parent=self)
        w.setToolTip("Define scanning regions. Hold Shift key to remove zone.")
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        group.addButton(w)
        group.setId(w, laser_studio.viewer.Mode.ZONE)
        self.addWidget(w)

        w = ColoredPushButton(":/icons/region_tilted.svg", parent=self)
        w.setToolTip("Define scanning regions (tilted rectangle)")
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        group.addButton(w)
        group.setId(w, laser_studio.viewer.Mode.ZONE_TILTED)
        self.addWidget(w)

        w = ColoredPushButton(":/icons/region_poly.svg", parent=self)
        w.setToolTip("Define scanning regions (polygon)")
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        group.addButton(w)
        group.setId(w, laser_studio.viewer.Mode.ZONE_POLY)
        self.addWidget(w)

        # Active zone selector: drawing gestures target the selected zone.
        self.zones = laser_studio.viewer.scans
        w = self.zone_combobox = QComboBox()
        w.setToolTip("Zone that the drawing tools add to or subtract from")
        w.setIconSize(QSize(16, 16))
        w.setMinimumContentsLength(10)
        w.currentIndexChanged.connect(self.__on_zone_selected)
        self.addWidget(w)

        w = QPushButton(self)
        w.setToolTip("Add a new scanning zone")
        w.setText("+")
        w.clicked.connect(self.__on_add_zone)
        self.addWidget(w)

        self.zones.zone_changed.connect(self.__sync_zones)
        self.__sync_zones()

        # Go-to-next position button
        w = QPushButton(self)
        w.setToolTip("Go to next Scan Point")
        w.setIcon(
            QIcon(colored_image(":/icons/fontawesome-free/forward-step-solid.svg"))
        )
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(laser_studio.handle_go_next)
        self.addWidget(w)

        # Scanning from LSAPI enable/disable button
        w = ColoredPushButton(":/icons/no-scan.svg", ":/icons/scan.svg", parent=self)
        w.setToolTip("Enable or block the go_next commands from LSAPI.")
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        w.setChecked(laser_studio.scanning_enabled)
        w.toggled.connect(lambda v: laser_studio.__setattr__("scanning_enabled", v))
        self.addWidget(w)

        # Color drop down menu
        w = self.color_combobox = QComboBox()
        w.setToolTip("Select the color of the scan path")
        w.setIconSize(QSize(24, 24))
        for color in LedgerColors:
            w.addItem(create_color_qicon(color), None, color.value)
        for color in [
            QColorConstants.Red,
            QColorConstants.Green,
            QColorConstants.Blue,
            QColorConstants.Yellow,
            QColorConstants.Magenta,
            QColorConstants.Cyan,
            QColorConstants.Black,
            QColorConstants.White,
        ]:
            w.addItem(create_color_qicon(color), None, color)
        w.currentIndexChanged.connect(
            lambda _: laser_studio.viewer.scan_geometry.__setattr__(
                "color", self.color_combobox.currentData()
            )
        )
        self.addWidget(w)

        # Density
        w = self.density = ReturnSpinBox()
        w.setToolTip(
            "Scan density. The bigger it is, the smaller average distance between consecutive points is."
        )
        w.setMinimum(1)
        w.setMaximum(1000)
        w.setValue(laser_studio.viewer.scan_geometry.scan_path_generator.density)
        w.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        w.returnPressed2.connect(
            lambda: laser_studio.viewer.scan_geometry.__setattr__(
                "density", self.density.value()
            )
        )
        w.reset()
        self.addWidget(w)

        # Size of markers
        w = self.size_sp = ReturnDoubleSpinBox()
        w.setSuffix("\xa0µm")
        w.setToolTip("Size of points in the scan path")
        w.setMinimum(0.1)
        w.setDecimals(1)
        w.setSingleStep(1.0)
        w.setMaximum(2000.0)
        w.setValue(laser_studio.viewer.default_marker_size)
        w.reset()
        w.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        w.returnPressed2.connect(
            lambda: laser_studio.viewer.scan_geometry.__setattr__(
                "diameter", self.size_sp.value()
            )
        )
        self.addWidget(w)

    def __on_add_zone(self):
        """Append a zone and make it the active one."""
        self.zones.active_zone = self.zones.add_zone()

    def __on_zone_selected(self, index: int):
        if self.__syncing or index < 0:
            return
        zone = self.zone_combobox.itemData(index)
        assert zone is not None and isinstance(zone, ScanZone)
        self.zones.active_zone = zone

    def __sync_zones(self):
        """Rebuild the zone list from the model."""
        self.__syncing = True
        try:
            self.zone_combobox.clear()
            for zone in self.zones.zones.values():
                self.zone_combobox.addItem(
                    create_color_qicon(zone.color), zone.name, zone
                )
        finally:
            self.__syncing = False
