from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColorConstants, QIcon, QColor
from PyQt6.QtWidgets import QToolBar, QPushButton, QSizePolicy, QMenu, QFileDialog
from ..return_line_edit import ReturnDoubleSpinBox
from ...utils.util import colored_image
from ..viewer import Viewer
from .markerslistdockwidget import MarkersListDockWidget
from ..coloredbutton import ColoredPushButton
from ...utils.colors import LedgerColors


class MarkersToolBar(QToolBar):
    def __init__(self, viewer: Viewer):
        super().__init__("Markers")
        self.setObjectName("toolbar-markers")  # For settings save and restore
        self.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.setFloatable(True)
        self.selected_color: QColor | Qt.GlobalColor | int | LedgerColors = (
            QColorConstants.Red
        )

        self.viewer = viewer

        # Add a marker
        self.add_marker_button = w = QPushButton(self)
        self.set_color(self.selected_color)
        w.setIconSize(QSize(24, 24))
        w.setToolTip("Add marker")
        w.clicked.connect(lambda: self.viewer.add_marker(color=self.selected_color))
        self.addWidget(w)

        # Clear all markers
        w = QPushButton(self)
        w.setIcon(QIcon(colored_image(":/icons/location-pin-clear.svg")))
        w.setIconSize(QSize(24, 24))
        w.setToolTip("Clear all markers")
        w.clicked.connect(self.viewer.clear_markers)
        self.addWidget(w)

        # Load/save markers menu
        w = QPushButton(self)
        w.setIcon(QIcon(colored_image(":/icons/location-pin-dots.svg")))
        w.setIconSize(QSize(24, 24))
        markers_menu = QMenu("Markers", self)
        markers_menu.addAction("Load markers from file", lambda: self.load_markers())
        markers_menu.addAction("Save markers to file", lambda: self.save_markers())
        # Submenu for setting the color of the markers
        self._color_menu = color_menu = QMenu("Set color for new markers", self)
        color_menu.addAction(
            "Safety Orange", lambda: self.set_color(LedgerColors.SafetyOrange)
        )
        color_menu.addAction(
            "Serenity Purple", lambda: self.set_color(LedgerColors.SerenityPurple)
        )
        color_menu.addAction(
            "Security Blue", lambda: self.set_color(LedgerColors.SecurityBlue)
        )
        color_menu.addAction("Grellow", lambda: self.set_color(LedgerColors.Grellow))
        color_menu.addAction("Red", lambda: self.set_color(QColorConstants.Red))
        color_menu.addAction("Green", lambda: self.set_color(QColorConstants.Green))
        color_menu.addAction("Blue", lambda: self.set_color(QColorConstants.Blue))
        color_menu.addAction("Yellow", lambda: self.set_color(QColorConstants.Yellow))
        color_menu.addAction("Magenta", lambda: self.set_color(QColorConstants.Magenta))
        color_menu.addAction("Cyan", lambda: self.set_color(QColorConstants.Cyan))
        color_menu.addAction("Black", lambda: self.set_color(QColorConstants.Black))
        color_menu.addAction("White", lambda: self.set_color(QColorConstants.White))
        markers_menu.addMenu(color_menu)
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
        self.marker_size_sp = w = ReturnDoubleSpinBox()
        self.marker_size_sp.setSuffix("\xa0µm")
        self.marker_size_sp.setToolTip("Markers' size")
        self.marker_size_sp.setMinimum(0.1)
        self.marker_size_sp.setDecimals(1)
        self.marker_size_sp.setSingleStep(10.0)
        self.marker_size_sp.setMaximum(2000.0)
        self.marker_size_sp.setValue(viewer.default_marker_size)
        self.marker_size_sp.reset()
        self.marker_size_sp.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )
        w.returnPressed.connect(lambda: viewer.marker_size(self.marker_size_sp.value()))
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

    def set_color(self, color: QColor | Qt.GlobalColor | int | LedgerColors):
        self.selected_color = color
        self.add_marker_button.setIcon(
            QIcon(
                colored_image(
                    ":/icons/location-pin-plus.svg", color=self.selected_color
                )
            )
        )
