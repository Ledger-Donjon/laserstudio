from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QToolBar, QPushButton
from ..return_line_edit import ReturnSpinBox
from ...utils.util import colored_image
from ..viewer import Viewer
from .markerslisttoolbar import MarkersListToolbar


class MarkersToolbar(QToolBar):
    def __init__(self, viewer: Viewer):
        super().__init__("Markers")
        self.setObjectName("toolbar-markers")  # For settings save and restore
        self.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.setFloatable(True)

        # Add a marker
        w = QPushButton(self)
        w.setIcon(QIcon(colored_image(":/icons/location-pin-plus.svg")))
        w.setIconSize(QSize(24, 24))
        w.setToolTip("Add marker")
        w.clicked.connect(lambda: viewer.add_marker())
        self.addWidget(w)

        # Clear all markers
        w = QPushButton(self)
        w.setIcon(QIcon(colored_image(":/icons/location-pin-clear.svg")))
        w.setIconSize(QSize(24, 24))
        w.setToolTip("Clear all markers")
        w.clicked.connect(viewer.clear_markers)
        self.addWidget(w)

        # Markers' size
        self.marker_size_sp = w = ReturnSpinBox()
        self.marker_size_sp.setSuffix("\xa0µm")
        self.marker_size_sp.setToolTip("Markers' size")
        self.marker_size_sp.setMinimum(1)
        self.marker_size_sp.setSingleStep(10)
        self.marker_size_sp.setMaximum(2000)
        self.marker_size_sp.setValue(int(viewer.default_marker_size))
        self.marker_size_sp.reset()
        w.returnPressed.connect(
            lambda: viewer.marker_size(float(self.marker_size_sp.value()))
        )
        self.addWidget(self.marker_size_sp)
