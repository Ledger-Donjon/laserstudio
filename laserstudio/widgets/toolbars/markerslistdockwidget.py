from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QPushButton,
    QDockWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QStyledItemDelegate,
    QAbstractItemView,
    QStyleOptionViewItem,
)
from PyQt6.QtCore import QModelIndex
from ..viewer import Viewer
from ..marker import Marker, IdMarker


class MarkersGroupListItem(QTreeWidgetItem):
    def __init__(self, parent: QTreeWidget | MarkersGroupListItem):
        super().__init__(parent)
        self.number_of_checked = 0
        self.setFlags(self.flags() & ~Qt.ItemFlag.ItemIsEditable)

    def update_checked_state(self):
        # To prevent the itemChanged signal from being emitted
        tw = self.treeWidget()
        assert tw is not None
        tw.blockSignals(True)
        self.setToolTip(0, f"{self.number_of_checked} shown over {self.childCount()}")
        tw.blockSignals(False)
        if self.number_of_checked == 0:
            self.setCheckState(0, Qt.CheckState.Unchecked)
        elif self.number_of_checked == self.childCount():
            self.setCheckState(0, Qt.CheckState.Checked)
        else:
            self.setCheckState(0, Qt.CheckState.PartiallyChecked)


class MarkersListItem(QTreeWidgetItem):
    def __init__(self, group: MarkersGroupListItem, marker: Marker):
        super().__init__(group)
        self.group = group
        self.marker = marker
        self.setFlags(self.flags() | Qt.ItemFlag.ItemIsEditable)
        visible = marker.isVisible()
        self.setCheckState(
            0, Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked
        )
        self.update_display()
        if visible:
            group.number_of_checked += 1

    def update_display(self) -> None:
        x, y = self.marker.pos().x(), self.marker.pos().y()
        label_text = self.marker.label or ""
        self.setText(1, label_text)
        self.setText(0, f"{x:.02f}\xa0µm, {y:.02f}\xa0µm")

        id_text = f"{self.marker.id} " if isinstance(self.marker, IdMarker) else ""
        label_tip = f"{self.marker.label} " if self.marker.label else ""
        self.setToolTip(
            0, f"Marker {id_text}{label_tip}at {x:.02f}\xa0µm, {y:.02f}\xa0µm"
        )
        self.setForeground(0, self.marker.qfillcolor)
        self.setForeground(1, self.marker.qfillcolor)


class _NonEditableColumnDelegate(QStyledItemDelegate):
    def createEditor(
        self,
        parent: QWidget | None,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ):
        if index.column() != 1:
            return None
        return super().createEditor(parent, option, index)


class MarkersListDockWidget(QDockWidget):
    def show_selected(self):
        for item in self.list.selectedItems():
            item.setCheckState(0, Qt.CheckState.Checked)

    def hide_selected(self):
        for item in self.list.selectedItems():
            item.setCheckState(0, Qt.CheckState.Unchecked)

    def refresh_list(self):
        self.list.clear()
        labeled_markers_by_color: dict[str, dict[str, list[Marker]]] = {}
        markers_by_colors: dict[str, list[Marker]] = {}
        for marker in self.viewer.markers:
            if type(marker.fillcolor) is QColor:
                name: str = f"{marker.fillcolor.hue():02x}{marker.fillcolor.saturation():02x}{marker.fillcolor.lightness():02x}{marker.fillcolor.alpha():02x}"
            else:
                name = str(marker.fillcolor)

            # Add unlabeled markers grouped by color
            if marker.label is None:
                if name not in markers_by_colors:
                    markers_by_colors[name] = [marker]
                else:
                    markers_by_colors[name].append(marker)
            else:
                # Add labeled markers grouped by color and label
                if marker.label not in labeled_markers_by_color:
                    labeled_markers_by_color[marker.label] = {}
                if name not in labeled_markers_by_color[marker.label]:
                    labeled_markers_by_color[marker.label][name] = [marker]
                else:
                    labeled_markers_by_color[marker.label][name].append(marker)

        # Add labeled markers grouped by color and label
        self.list.itemChanged.disconnect(self.item_changed)
        for label in sorted(labeled_markers_by_color.keys()):
            number_of_markers = 0
            labeled_group = MarkersGroupListItem(self.list)
            labeled_group.setFirstColumnSpanned(True)

            for color in sorted(labeled_markers_by_color[label].keys()):
                labeled_markers: list[Marker] = labeled_markers_by_color[label][color]
                color_group = MarkersGroupListItem(labeled_group)
                color_group.setForeground(0, labeled_markers[0].fillcolor)
                color_group.setText(
                    0,
                    f"{len(labeled_markers)} marker"
                    + ("" if len(labeled_markers) == 1 else "s"),
                )
                color_group.setFirstColumnSpanned(True)
                for marker in labeled_markers:
                    MarkersListItem(color_group, marker)
                color_group.update_checked_state()
                number_of_markers += len(labeled_markers)

            labeled_group.setText(
                0,
                label
                + f" - {number_of_markers} marker"
                + ("" if number_of_markers == 1 else "s"),
            )
            labeled_group.update_checked_state()

        # Add unlabeled markers grouped by color
        for color in sorted(markers_by_colors.keys()):
            markers: list[Marker] = markers_by_colors[color]
            group = MarkersGroupListItem(self.list)
            group.setForeground(0, markers[0].fillcolor)
            group.setText(
                0, f"{len(markers)} marker" + ("" if len(markers) == 1 else "s")
            )
            group.setFirstColumnSpanned(True)

            for marker in markers:
                MarkersListItem(group, marker)
            group.update_checked_state()
        self.list.itemChanged.connect(self.item_changed)

    def __init__(self, viewer: Viewer):
        super().__init__("Markers List")
        self.setObjectName("toolbar-markers-list")  # For settings save and restore
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self.viewer = viewer
        self.list = QTreeWidget()
        self.list.setHeaderLabels(["Position", "Label"])
        self.list.setColumnCount(2)
        self.list.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.list.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.list.setItemDelegateForColumn(0, _NonEditableColumnDelegate(self.list))
        self.list.itemChanged.connect(self.item_changed)

        w = QWidget()
        self.setWidget(w)
        vbox = QVBoxLayout()
        w.setLayout(vbox)

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
        if isinstance(item, MarkersListItem):
            self.viewer.follow_stage_sight = False
            self.viewer.cam_pos_zoom = item.marker.pos(), self.viewer.cam_pos_zoom[1]

    def item_changed(self, item: QTreeWidgetItem, column: int | None = None):
        if isinstance(item, MarkersListItem):
            if column in (0, None):
                new_label = item.text(0).strip()
                new_label = new_label if new_label else None
                if new_label != item.marker.label:
                    item.marker.label = new_label
                    item.marker.update_tooltip()
                    self.list.blockSignals(True)
                    item.update_display()
                    self.list.blockSignals(False)

            visible = item.checkState(0) == Qt.CheckState.Checked
            was_visible = item.marker.isVisible()
            if not was_visible and visible:
                item.group.number_of_checked += 1
            elif was_visible and not visible:
                item.group.number_of_checked -= 1
            item.marker.setVisible(visible)
            item.group.update_checked_state()
        if isinstance(item, MarkersGroupListItem):
            new_state = item.checkState(0)
            if new_state == Qt.CheckState.PartiallyChecked:
                return
            for i in range(item.childCount()):
                child = item.child(i)
                if child is None:
                    continue
                child.setCheckState(0, new_state)
