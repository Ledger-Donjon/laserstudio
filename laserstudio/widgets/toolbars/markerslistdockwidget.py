from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..markerslist import MarkersView, _MarkerNode, _TreeNode
from ..viewer import Viewer


class MarkersListDockWidget(QDockWidget):
    def __init__(self, viewer: Viewer):
        super().__init__("Markers List")
        self.setObjectName("toolbar-markers-list")  # For settings save and restore
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self.viewer = viewer
        self.list = MarkersView(viewer)
        self.model = self.list.markers_model

        w = QWidget()
        self.setWidget(w)
        vbox = QVBoxLayout()
        w.setLayout(vbox)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_list)
        vbox.addWidget(refresh_btn)

        hbox = QHBoxLayout()
        show_btn = QPushButton("Show")
        show_btn.clicked.connect(self.show_selected)
        hbox.addWidget(show_btn)
        hide_btn = QPushButton("Hide")
        hide_btn.clicked.connect(self.hide_selected)
        hbox.addWidget(hide_btn)
        vbox.addLayout(hbox)

        self.refresh_progress = QProgressBar()
        self.refresh_progress.setFormat("Refreshing...")
        self.refresh_progress.setVisible(False)
        vbox.addWidget(self.refresh_progress)
        vbox.addWidget(self.list)

    def _set_refreshing(self, refreshing: bool) -> None:
        self.refresh_progress.setVisible(refreshing)
        if refreshing:
            self.refresh_progress.setRange(0, 0)
        else:
            self.refresh_progress.setRange(0, 1)
            self.refresh_progress.setValue(0)
        self.list.setEnabled(not refreshing)

    def show_selected(self) -> None:
        self.list.set_visible(self._selected_nodes(), True)

    def hide_selected(self) -> None:
        self.list.set_visible(self._selected_nodes(), False)

    def _selected_nodes(self) -> list[_TreeNode]:
        return self.list._selected_nodes()

    def refresh_list(self) -> None:
        self._set_refreshing(True)
        self.list.reload()
        self._set_refreshing(False)

    def show_marker_node(self, node: _MarkerNode) -> None:
        self.list.center_on(node)
