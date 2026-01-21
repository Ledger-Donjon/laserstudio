from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QToolBar, QPushButton, QSizePolicy, QMenu, QFileDialog
from ..return_line_edit import ReturnSpinBox
from ...utils.util import colored_image
from ..viewer import Viewer
from .markerslistdockwidget import MarkersListDockWidget
from ..coloredbutton import ColoredPushButton


class MarkersToolBar(QToolBar):
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

        # Load/save markers menu
        w = QPushButton(self)
        w.setIcon(QIcon(colored_image(":/icons/location-pin-dots.svg")))
        w.setIconSize(QSize(24, 24))
        markers_menu = QMenu("Markers", self)
        markers_menu.addAction("Load markers from file", lambda: self.load_markers())
        markers_menu.addAction("Save markers to file", lambda: self.save_markers())
        w.setMenu(markers_menu)
        self.addWidget(w)

        # Show list of all markers
        w = ColoredPushButton(parent=self)
        w.setText("Show list")
        w.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        w.setToolTip("Show a list of all markers")
        w.setCheckable(True)
        w.clicked.connect(self.show_markers_list)
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
        self.marker_size_sp.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )
        w.returnPressed.connect(
            lambda: viewer.marker_size(float(self.marker_size_sp.value()))
        )
        self.addWidget(self.marker_size_sp)

        # Dock widget: Markers' List
        self.markers_list_dockwidget = MarkersListDockWidget(viewer)

    def show_markers_list(self, state: bool):
        if state:
            self.markers_list_dockwidget.refresh_list()
            self.markers_list_dockwidget.show()
        else:
            self.markers_list_dockwidget.hide()

    def load_markers(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load markers from file",
            "",
            "Markers files (*.json)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self.viewer.load_markers(file_path)

    def save_markers(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save markers to file",
            "",
            "Markers files (*.json)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self.viewer.save_markers(file_path)
