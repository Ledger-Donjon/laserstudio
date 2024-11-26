from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QPushButton, QDialog, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QHBoxLayout
from ..viewer import Viewer
from ..marker import Marker

class MarkerGroupListItem(QTreeWidgetItem):
    def __init__(self, parent: QTreeWidget):
        super().__init__(parent)
        self._number_of_checked = 0

    @property
    def number_of_checked(self):
        return self._number_of_checked
    
    @number_of_checked.setter
    def number_of_checked(self, value):
        self._number_of_checked = value

    def update_checked_state(self):
        self.treeWidget().blockSignals(True)
        self.setToolTip(0, f"{self._number_of_checked} shown over {self.childCount()}")
        self.treeWidget().blockSignals(False)
        if self._number_of_checked == 0:
            self.setCheckState(0, Qt.CheckState.Unchecked)
        elif self._number_of_checked == self.childCount():
            self.setCheckState(0, Qt.CheckState.Checked)
        else:
            self.setCheckState(0, Qt.CheckState.PartiallyChecked)


class MarkerListItem(QTreeWidgetItem):
    def __init__(self, group: MarkerGroupListItem, marker: Marker):
        super().__init__(group)
        self.group = group
        x, y  = marker.pos().x(), marker.pos().y()
        self.marker = marker
        visible = marker.isVisible()
        self.setCheckState(0, Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked)
        self.setText(0, f"{x:.02f}\xA0µm, {y:.02f}\xA0µm")
        self.setForeground(0, marker.fillcolor)
        if visible:
            group.number_of_checked += 1

class MarkerListDialog(QDialog):
    def open(self):
        super().open()
        self.refresh_list()
        self.activateWindow()

    def show_selected(self):
        for item in self.list.selectedItems():
            item.setCheckState(0, Qt.CheckState.Checked)

    def hide_selected(self):
        for item in self.list.selectedItems():
            item.setCheckState(0, Qt.CheckState.Unchecked)

    def refresh_list(self):
        self.list.clear()
        markers_by_colors: dict[str, list[Marker]] = {}
        for marker in self.viewer.markers:
            if type(marker.fillcolor) is QColor:
                name: str = f"{marker.fillcolor.hue():02x}{marker.fillcolor.saturation():02x}{marker.fillcolor.lightness():02x}{marker.fillcolor.alpha():02x}"
            else:
                name = str(marker.color)
            if name not in markers_by_colors:
                markers_by_colors[name] = [marker]
            else:
                markers_by_colors[name].append(marker)
        for color in sorted(markers_by_colors.keys()):
            markers: list[Marker] = markers_by_colors[color]
            group = MarkerGroupListItem(self.list)
            group.setForeground(0, markers[0].fillcolor)
            group.setText(0, f"{len(markers)} marker" + ("" if len(markers) == 1 else "s"))

            self.list.itemChanged.disconnect(self.item_changed)
            for marker in markers:
                MarkerListItem(group, marker)
            group.update_checked_state()
            self.list.itemChanged.connect(self.item_changed)


    def __init__(self, viewer: Viewer):
        super().__init__()
        self.viewer = viewer
        self.list = QTreeWidget()
        self.list.setHeaderHidden(True)
        self.list.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.list.itemChanged.connect(self.item_changed)

        vbox = QVBoxLayout()
        self.setLayout(vbox)
        
        w = QPushButton("Refresh")
        w.clicked.connect(self.refresh_list)
        vbox.addWidget(w)

        hbox = QHBoxLayout()
        w = QPushButton("Show")
        w.clicked.connect(self.show_selected)
        hbox.addWidget(w)
        w = QPushButton("Hide")
        w.clicked.connect(self.hide_selected)
        hbox.addWidget(w)
        vbox.addLayout(hbox)
        vbox.addWidget(self.list)
        self.list.itemDoubleClicked.connect(self.show_marker)
    
    def show_marker(self, item: QTreeWidgetItem):
        if isinstance(item, MarkerListItem):
            self.viewer.follow_stage_sight = False
            self.viewer.cam_pos_zoom = item.marker.pos(), self.viewer.cam_pos_zoom[1]

    def item_changed(self, item: QTreeWidgetItem):
        if isinstance(item, MarkerListItem):
            visible = item.checkState(0) == Qt.CheckState.Checked
            was_visible = item.marker.isVisible()
            if not was_visible and visible:
                item.group.number_of_checked += 1
            elif was_visible and not visible:
                item.group.number_of_checked -= 1
            item.marker.setVisible(visible)
            item.group.update_checked_state()
        if isinstance(item, MarkerGroupListItem):
            new_state = item.checkState(0)
            if new_state == Qt.CheckState.PartiallyChecked: return
            for i in range(item.childCount()):
                child = item.child(i)
                if child is None: continue
                child.setCheckState(0, new_state)
    
