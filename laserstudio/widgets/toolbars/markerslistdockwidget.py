from __future__ import annotations

from typing import Iterator, Sequence

from PyQt6.QtCore import (
    Qt,
    QModelIndex,
    QPoint,
    QAbstractItemModel,
    QItemSelectionModel,
)
from PyQt6.QtGui import QColor, QAction
from PyQt6.QtWidgets import (
    QPushButton,
    QDockWidget,
    QTreeView,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QAbstractItemView,
    QMenu,
    QApplication,
    QProgressBar,
)
from ..viewer import Viewer
from ..marker import Marker, IdMarker


class _TreeNode:
    def __init__(self, parent: _GroupNode | None):
        self.parent = parent
        self.row = 0


class _GroupNode(_TreeNode):
    def __init__(
        self,
        parent: _GroupNode | None,
        name: str,
        fillcolor: QColor | Qt.GlobalColor | int | None = None,
    ):
        super().__init__(parent)
        self.name = name
        self.fillcolor = fillcolor
        self.children: list[_TreeNode] = []
        self.total_count = 0
        self.visible_count = 0

    def add_child(self, child: _TreeNode) -> None:
        child.parent = self
        child.row = len(self.children)
        self.children.append(child)

    def iter_group_nodes(self) -> Iterator["_GroupNode"]:
        for child in self.children:
            if isinstance(child, _GroupNode):
                yield child
                yield from child.iter_group_nodes()

    def iter_marker_nodes(self) -> Iterator["_MarkerNode"]:
        for child in self.children:
            if isinstance(child, _MarkerNode):
                yield child
            elif isinstance(child, _GroupNode):
                yield from child.iter_marker_nodes()


class _MarkerNode(_TreeNode):
    def __init__(self, parent: _GroupNode, marker: Marker):
        super().__init__(parent)
        self.marker = marker


class MarkersTreeModel(QAbstractItemModel):
    _headers = ["Id", "Position", "Label"]

    def __init__(self, viewer: Viewer):
        super().__init__()
        self._viewer = viewer
        self._root = _GroupNode(None, "root")

    def _color_key(self, marker: Marker) -> str:
        if isinstance(marker.fillcolor, QColor):
            return (
                f"{marker.fillcolor.hue():02x}"
                f"{marker.fillcolor.saturation():02x}"
                f"{marker.fillcolor.lightness():02x}"
                f"{marker.fillcolor.alpha():02x}"
            )
        return str(marker.fillcolor)

    def _marker_id_text(self, marker: Marker) -> str:
        return f"#{marker.id} " if isinstance(marker, IdMarker) else ""

    def _group_label(self, count: int) -> str:
        return f"{count} marker" + ("" if count == 1 else "s")

    def _label_group_label(self, label: str, count: int) -> str:
        return f"{label} - {self._group_label(count)}"

    def set_markers(self, markers: Sequence[Marker]) -> None:
        labeled_markers_by_color: dict[str, dict[str, list[Marker]]] = {}
        markers_by_colors: dict[str, list[Marker]] = {}

        def marker_sort_key(marker: Marker) -> int:
            return marker.id if isinstance(marker, IdMarker) else 0

        for marker in sorted(markers, key=marker_sort_key):
            key = self._color_key(marker)
            if marker.label is None:
                markers_by_colors.setdefault(key, []).append(marker)
            else:
                labeled_markers_by_color.setdefault(marker.label, {}).setdefault(
                    key, []
                ).append(marker)

        self.beginResetModel()
        self._root = _GroupNode(None, "root")

        for label in sorted(labeled_markers_by_color.keys()):
            label_group = _GroupNode(self._root, "")
            self._root.add_child(label_group)
            total_count = 0
            visible_count = 0

            for color in sorted(labeled_markers_by_color[label].keys()):
                markers_list = labeled_markers_by_color[label][color]
                color_group = _GroupNode(
                    label_group, "", fillcolor=markers_list[0].fillcolor
                )
                label_group.add_child(color_group)

                for marker in markers_list:
                    color_group.add_child(_MarkerNode(color_group, marker))

                color_group.total_count = len(markers_list)
                color_group.visible_count = sum(
                    1 for marker in markers_list if marker.isVisible()
                )
                color_group.name = self._group_label(color_group.total_count)
                total_count += color_group.total_count
                visible_count += color_group.visible_count

            label_group.total_count = total_count
            label_group.visible_count = visible_count
            label_group.name = self._label_group_label(label, total_count)

        for color in sorted(markers_by_colors.keys()):
            markers_list = markers_by_colors[color]
            group = _GroupNode(self._root, "", fillcolor=markers_list[0].fillcolor)
            self._root.add_child(group)

            for marker in markers_list:
                group.add_child(_MarkerNode(group, marker))

            group.total_count = len(markers_list)
            group.visible_count = sum(
                1 for marker in markers_list if marker.isVisible()
            )
            group.name = self._group_label(group.total_count)

        self._root.total_count = sum(
            child.total_count
            for child in self._root.children
            if isinstance(child, _GroupNode)
        )
        self._root.visible_count = sum(
            child.visible_count
            for child in self._root.children
            if isinstance(child, _GroupNode)
        )
        self.endResetModel()

    def node_from_index(self, index: QModelIndex) -> _TreeNode | None:
        if not index.isValid():
            return None
        return index.internalPointer()

    def index_from_node(self, node: _TreeNode, column: int = 0) -> QModelIndex:
        if node is self._root:
            return QModelIndex()
        return self.createIndex(node.row, column, node)

    def index(
        self,
        row: int,
        column: int,
        parent: QModelIndex = QModelIndex(),
    ) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parent_node = self._root if not parent.isValid() else parent.internalPointer()
        if not isinstance(parent_node, _GroupNode):
            return QModelIndex()
        if row >= len(parent_node.children):
            return QModelIndex()
        child = parent_node.children[row]
        return self.createIndex(row, column, child)

    def parent(self, child: QModelIndex) -> QModelIndex:  # type: ignore[override]
        if not child.isValid():
            return QModelIndex()
        node = child.internalPointer()
        if not isinstance(node, _TreeNode):
            return QModelIndex()
        parent_node = node.parent
        if parent_node is None or parent_node is self._root:
            return QModelIndex()
        return self.createIndex(parent_node.row, 0, parent_node)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if not parent.isValid():
            return len(self._root.children)
        node = parent.internalPointer()
        if isinstance(node, _GroupNode):
            return len(node.children)
        return 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._headers)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and section < len(self._headers):
            return self._headers[section]
        return None

    def _group_check_state(self, group: _GroupNode) -> Qt.CheckState:
        if group.total_count == 0 or group.visible_count == 0:
            return Qt.CheckState.Unchecked
        if group.visible_count == group.total_count:
            return Qt.CheckState.Checked
        return Qt.CheckState.PartiallyChecked

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        node = index.internalPointer()
        column = index.column()

        if isinstance(node, _MarkerNode):
            marker = node.marker
            if role == Qt.ItemDataRole.DisplayRole:
                if column == 0:
                    return self._marker_id_text(marker)
                if column == 1:
                    x, y = marker.pos().x(), marker.pos().y()
                    return f"{x:.02f}\xa0µm, {y:.02f}\xa0µm"
                if column == 2:
                    return marker.label or ""
            if role == Qt.ItemDataRole.EditRole and column == 2:
                return marker.label or ""
            if role == Qt.ItemDataRole.ForegroundRole:
                return marker.qfillcolor
            if role == Qt.ItemDataRole.ToolTipRole:
                x, y = marker.pos().x(), marker.pos().y()
                label_tip = f"{marker.label} " if marker.label else ""
                id_text = self._marker_id_text(marker)
                return (
                    f"Marker #{id_text}{label_tip}"
                    f"at {x:.02f}\xa0µm, {y:.02f}\xa0µm"
                )
            if role == Qt.ItemDataRole.CheckStateRole and column == 0:
                return (
                    Qt.CheckState.Checked
                    if marker.isVisible()
                    else Qt.CheckState.Unchecked
                )
            return None

        if isinstance(node, _GroupNode):
            if role == Qt.ItemDataRole.DisplayRole:
                return node.name if column == 0 else ""
            if role == Qt.ItemDataRole.ForegroundRole and column == 0:
                return node.fillcolor
            if role == Qt.ItemDataRole.ToolTipRole and node.total_count > 0:
                return f"{node.visible_count} shown over {node.total_count}"
            if role == Qt.ItemDataRole.CheckStateRole and column == 0:
                return self._group_check_state(node)
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        node = index.internalPointer()
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        if isinstance(node, _MarkerNode) and index.column() == 2:
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def _emit_group_updates(self, group: _GroupNode | None) -> None:
        while group is not None and group is not self._root:
            index = self.index_from_node(group, 0)
            self.dataChanged.emit(
                index,
                index,
                [Qt.ItemDataRole.CheckStateRole, Qt.ItemDataRole.ToolTipRole],
            )
            group = group.parent

    def _emit_descendant_check_updates(self, group: _GroupNode) -> None:
        if not group.children:
            return
        left = self.index_from_node(group.children[0], 0)
        right = self.index_from_node(group.children[-1], self.columnCount() - 1)
        self.dataChanged.emit(left, right, [Qt.ItemDataRole.CheckStateRole])
        for child in group.children:
            if isinstance(child, _GroupNode):
                child_index = self.index_from_node(child, 0)
                self.dataChanged.emit(
                    child_index,
                    child_index,
                    [Qt.ItemDataRole.CheckStateRole, Qt.ItemDataRole.ToolTipRole],
                )
                self._emit_descendant_check_updates(child)

    def _set_group_visibility(self, group: _GroupNode, visible: bool) -> None:
        old_visible = group.visible_count
        new_visible = group.total_count if visible else 0
        if old_visible == new_visible:
            return

        for marker_node in group.iter_marker_nodes():
            if marker_node.marker.isVisible() != visible:
                marker_node.marker.setVisible(visible)

        group.visible_count = group.total_count if visible else 0
        for group_node in group.iter_group_nodes():
            group_node.visible_count = group_node.total_count if visible else 0

        delta = new_visible - old_visible
        parent = group.parent
        while parent is not None:
            parent.visible_count += delta
            parent = parent.parent

        self._emit_group_updates(group)
        self._emit_descendant_check_updates(group)

    def _toggle_marker_visibility(self, node: _MarkerNode, visible: bool) -> None:
        if node.marker.isVisible() == visible:
            return
        node.marker.setVisible(visible)
        delta = 1 if visible else -1
        parent = node.parent
        while parent is not None:
            parent.visible_count += delta
            parent = parent.parent

    def setData(
        self,
        index: QModelIndex,
        value: object,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if not index.isValid():
            return False
        node = index.internalPointer()

        if isinstance(node, _MarkerNode):
            if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
                if isinstance(value, Qt.CheckState):
                    state = value
                elif isinstance(value, int):
                    state = Qt.CheckState(value)
                else:
                    return False
                visible = state == Qt.CheckState.Checked
                self._toggle_marker_visibility(node, visible)
                self.dataChanged.emit(
                    index, index, [Qt.ItemDataRole.CheckStateRole]
                )
                self._emit_group_updates(node.parent)
                return True
            if role == Qt.ItemDataRole.EditRole and index.column() == 2:
                new_label = str(value).strip()
                new_label = new_label if new_label else None
                if new_label != node.marker.label:
                    node.marker.label = new_label
                    node.marker.update_tooltip()
                    left = self.index_from_node(node, 0)
                    right = self.index_from_node(node, self.columnCount() - 1)
                    self.dataChanged.emit(
                        left,
                        right,
                        [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole],
                    )
                return True

        if isinstance(node, _GroupNode):
            if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
                if isinstance(value, Qt.CheckState):
                    new_state = value
                elif isinstance(value, int):
                    new_state = Qt.CheckState(value)
                else:
                    return False
                if new_state == Qt.CheckState.PartiallyChecked:
                    return False
                self._set_group_visibility(node, new_state == Qt.CheckState.Checked)
                return True

        return False


class MarkersListDockWidget(QDockWidget):
    def __init__(self, viewer: Viewer):
        super().__init__("Markers List")
        self.setObjectName("toolbar-markers-list")  # For settings save and restore
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self.viewer = viewer
        self.list = QTreeView()
        self.model = MarkersTreeModel(self.viewer)
        self.list.setModel(self.model)
        self.list.setUniformRowHeights(True)
        self.list.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.list.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.show_context_menu)

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
        self.refresh_progress = QProgressBar()
        self.refresh_progress.setFormat("Refreshing...")
        self.refresh_progress.setVisible(False)
        vbox.addWidget(self.refresh_progress)
        vbox.addWidget(self.list)

        self.list.doubleClicked.connect(self.show_marker_index)

    def _set_refreshing(self, refreshing: bool) -> None:
        self.refresh_progress.setVisible(refreshing)
        if refreshing:
            self.refresh_progress.setRange(0, 0)
        else:
            self.refresh_progress.setRange(0, 1)
            self.refresh_progress.setValue(0)
        self.list.setEnabled(not refreshing)

    def _selected_nodes(self) -> list[_TreeNode]:
        selection_model = self.list.selectionModel()
        if selection_model is None:
            return []
        nodes: list[_TreeNode] = []
        seen: set[int] = set()
        for index in selection_model.selectedRows(0):
            node = self.model.node_from_index(index)
            if node is None:
                continue
            node_id = id(node)
            if node_id in seen:
                continue
            seen.add(node_id)
            nodes.append(node)
        return nodes

    def _set_nodes_visible(
        self, nodes: Sequence[_TreeNode], visible: bool
    ) -> None:
        new_state = (
            Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked
        )
        for node in nodes:
            index = self.model.index_from_node(node, 0)
            if index.isValid():
                self.model.setData(
                    index, new_state, Qt.ItemDataRole.CheckStateRole
                )

    def _remove_marker_nodes(self, nodes: list[_MarkerNode]) -> None:
        for node in nodes:
            if isinstance(node.marker, IdMarker):
                node.marker.remove()
        self.refresh_list()

    def show_selected(self):
        self._set_nodes_visible(self._selected_nodes(), True)

    def hide_selected(self):
        self._set_nodes_visible(self._selected_nodes(), False)

    def show_context_menu(self, position: QPoint) -> None:
        index = self.list.indexAt(position)
        if not index.isValid():
            return

        selection_model = self.list.selectionModel()
        if selection_model is None:
            return
        if not selection_model.isSelected(index):
            selection_model.clearSelection()
            selection_model.select(
                index,
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows,
            )

        node = self.model.node_from_index(index)
        if node is None:
            return

        menu = QMenu(self.list)
        if isinstance(node, _MarkerNode):
            marker_nodes = [
                selected
                for selected in self._selected_nodes()
                if isinstance(selected, _MarkerNode)
            ]
            if not marker_nodes:
                return

            go_action = QAction("Go to marker", menu)
            go_action.setEnabled(len(marker_nodes) == 1)
            if len(marker_nodes) == 1:
                go_action.triggered.connect(
                    lambda: self.show_marker_node(marker_nodes[0])
                )
            menu.addAction(go_action)

            menu.addSeparator()
            menu.addAction(
                "Show",
                lambda: self._set_nodes_visible(marker_nodes, True),
            )
            menu.addAction(
                "Hide",
                lambda: self._set_nodes_visible(marker_nodes, False),
            )

            rename_action = QAction("Rename label...", menu)
            rename_action.setEnabled(len(marker_nodes) == 1)
            if len(marker_nodes) == 1:
                rename_action.triggered.connect(
                    lambda: self.list.edit(
                        self.model.index_from_node(marker_nodes[0], 2)
                    )
                )
            menu.addAction(rename_action)

            menu.addSeparator()
            remove_label = (
                "Remove marker" if len(marker_nodes) == 1 else "Remove markers"
            )
            menu.addAction(
                remove_label,
                lambda: self._remove_marker_nodes(marker_nodes),
            )
        elif isinstance(node, _GroupNode):
            group_nodes = [
                selected
                for selected in self._selected_nodes()
                if isinstance(selected, _GroupNode)
            ]
            if not group_nodes:
                return
            menu.addAction(
                "Show all",
                lambda: self._set_nodes_visible(group_nodes, True),
            )
            menu.addAction(
                "Hide all",
                lambda: self._set_nodes_visible(group_nodes, False),
            )
        else:
            return

        viewport = self.list.viewport()
        if viewport is None:
            return
        menu.exec(viewport.mapToGlobal(position))

    def refresh_list(self):
        self._set_refreshing(True)
        QApplication.processEvents()
        self.model.set_markers(self.viewer.markers)
        self._set_refreshing(False)

    def show_marker_node(self, node: _MarkerNode):
        self.viewer.follow_stage_sight = False
        self.viewer.cam_pos_zoom = node.marker.pos(), self.viewer.cam_pos_zoom[1]

    def show_marker_index(self, index: QModelIndex):
        node = self.model.node_from_index(index)
        if isinstance(node, _MarkerNode):
            self.show_marker_node(node)

