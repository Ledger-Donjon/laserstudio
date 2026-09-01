"""
List of the rulers present in a viewer, shared by both interfaces.

:class:`RulersTableModel` exposes the viewer's rulers as a flat table, and
:class:`RulersView` is the tree view (with its context menu) embedded either in
the classic window's dock widget or in the new UI's Analyze panel. Rulers are
few and are edited by dragging their endpoints, so the model follows the viewer
signals and refreshes itself instead of offering a manual refresh.
"""
from __future__ import annotations

from typing import Sequence

from PyQt6.QtCore import (
    QAbstractTableModel,
    QItemSelectionModel,
    QModelIndex,
    QObject,
    QPoint,
    Qt,
)
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTreeView, QWidget

from .ruler import Ruler, format_length
from .viewer import Viewer


class RulersTableModel(QAbstractTableModel):
    """Flat table over the rulers of a viewer."""

    _headers = ["Id", "Distance", "Graduation", "Nb graduations", "Label"]

    COL_ID = 0
    COL_DISTANCE = 1
    COL_GRADUATION = 2
    COL_COUNT = 3
    COL_LABEL = 4

    def __init__(self, viewer: Viewer, parent: QObject | None = None):
        super().__init__(parent)
        self._viewer = viewer
        self._rulers: list[Ruler] = []
        viewer.rulers_changed.connect(self.reload)
        self.reload()

    def reload(self) -> None:
        """Rebuild the row list from the viewer."""
        for ruler in self._rulers:
            try:
                ruler.changed.disconnect(self._on_ruler_changed)
            except TypeError:
                # Already disconnected (e.g. the ruler was removed).
                pass

        self.beginResetModel()
        self._rulers = self._viewer.rulers
        self.endResetModel()

        for ruler in self._rulers:
            ruler.changed.connect(self._on_ruler_changed)

    def ruler_from_index(self, index: QModelIndex) -> Ruler | None:
        if not index.isValid() or index.row() >= len(self._rulers):
            return None
        return self._rulers[index.row()]

    def _on_ruler_changed(self) -> None:
        ruler = self.sender()
        if not isinstance(ruler, Ruler):
            return
        try:
            row = self._rulers.index(ruler)
        except ValueError:
            return
        self.dataChanged.emit(
            self.index(row, 0), self.index(row, self.columnCount() - 1)
        )

    def set_visible(self, rulers: Sequence[Ruler], visible: bool) -> None:
        """Show or hide the given rulers and refresh their rows."""
        for ruler in rulers:
            if ruler.isVisible() == visible:
                continue
            ruler.setVisible(visible)
            try:
                row = self._rulers.index(ruler)
            except ValueError:
                continue
            index = self.index(row, self.COL_ID)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])

    # -- QAbstractTableModel ---------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rulers)

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

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        ruler = self.ruler_from_index(index)
        if ruler is None:
            return None
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if column == self.COL_ID:
                return f"#{ruler.id}"
            if column == self.COL_DISTANCE:
                return format_length(ruler.length)
            if column == self.COL_GRADUATION:
                interval = ruler.effective_graduation
                return "—" if interval is None else format_length(interval)
            if column == self.COL_COUNT:
                count = ruler.effective_graduation_count
                return "—" if count is None else f"{count:.02f}"
            if column == self.COL_LABEL:
                return ruler.label or ""
        if role == Qt.ItemDataRole.EditRole and column == self.COL_LABEL:
            return ruler.label or ""
        if role == Qt.ItemDataRole.FontRole:
            return self._font_for(ruler, column)
        if role == Qt.ItemDataRole.ForegroundRole:
            return ruler.qcolor
        if role == Qt.ItemDataRole.ToolTipRole:
            return ruler.tooltip
        if role == Qt.ItemDataRole.CheckStateRole and column == self.COL_ID:
            return (
                Qt.CheckState.Checked
                if ruler.isVisible()
                else Qt.CheckState.Unchecked
            )
        return None

    def _font_for(self, ruler: Ruler, column: int) -> QFont | None:
        """Bold the graduation form that is fixed on this ruler.

        The other column holds the value derived from it, which moves when the
        ruler is resized, so only the fixed one is emphasized.
        """
        fixed = (column == self.COL_GRADUATION and ruler.graduation is not None) or (
            column == self.COL_COUNT and ruler.graduation_count is not None
        )
        if not fixed:
            return None
        # Derive from the view font so the stylesheet size is kept.
        parent = self.parent()
        font = QFont(parent.font() if isinstance(parent, QWidget) else QFont())
        font.setBold(True)
        return font

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == self.COL_ID:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        if index.column() == self.COL_LABEL:
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(
        self,
        index: QModelIndex,
        value: object,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        ruler = self.ruler_from_index(index)
        if ruler is None:
            return False

        if role == Qt.ItemDataRole.CheckStateRole and index.column() == self.COL_ID:
            if isinstance(value, Qt.CheckState):
                state = value
            elif isinstance(value, int):
                state = Qt.CheckState(value)
            else:
                return False
            self.set_visible([ruler], state == Qt.CheckState.Checked)
            return True

        if role == Qt.ItemDataRole.EditRole and index.column() == self.COL_LABEL:
            # The label setter emits Ruler.changed, which refreshes the row.
            ruler.label = str(value).strip()
            return True

        return False


class RulersView(QTreeView):
    """Tree view over the rulers of a viewer, with a per-ruler context menu."""

    def __init__(self, viewer: Viewer, parent: QWidget | None = None):
        super().__init__(parent)
        self.viewer = viewer
        self.rulers_model = RulersTableModel(viewer, self)
        self.setModel(self.rulers_model)
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)
        self.setAllColumnsShowFocus(True)
        self.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.doubleClicked.connect(self._on_double_clicked)

    def _selected_rulers(self) -> list[Ruler]:
        selection_model = self.selectionModel()
        if selection_model is None:
            return []
        rulers: list[Ruler] = []
        for index in selection_model.selectedRows(0):
            ruler = self.rulers_model.ruler_from_index(index)
            if ruler is not None and ruler not in rulers:
                rulers.append(ruler)
        return rulers

    def center_on(self, ruler: Ruler) -> None:
        """Center the view on the middle of the ruler, keeping the zoom."""
        self.viewer.follow_stage_sight = False
        self.viewer.cam_pos_zoom = ruler.midpoint, self.viewer.cam_pos_zoom[1]

    def _on_double_clicked(self, index: QModelIndex) -> None:
        # The label column opens the inline editor instead of moving the view.
        if index.column() == RulersTableModel.COL_LABEL:
            return
        ruler = self.rulers_model.ruler_from_index(index)
        if ruler is not None:
            self.center_on(ruler)

    def _remove_rulers(self, rulers: Sequence[Ruler]) -> None:
        for ruler in rulers:
            ruler.remove()

    def show_context_menu(self, position: QPoint) -> None:
        index = self.indexAt(position)
        if not index.isValid():
            return

        selection_model = self.selectionModel()
        if selection_model is None:
            return
        if not selection_model.isSelected(index):
            selection_model.clearSelection()
            selection_model.select(
                index,
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows,
            )

        rulers = self._selected_rulers()
        if not rulers:
            return

        model = self.rulers_model
        menu = QMenu(self)
        if len(rulers) == 1:
            ruler = rulers[0]
            menu.addSection(f"Ruler #{ruler.id}")
            _ = menu.addAction("Go to ruler", lambda: self.center_on(ruler))
            menu.addSeparator()
            _ = menu.addAction("Show", lambda: model.set_visible(rulers, True))
            _ = menu.addAction("Hide", lambda: model.set_visible(rulers, False))
            menu.addSeparator()
            ruler.fill_menu(menu, self)
        else:
            _ = menu.addAction("Show", lambda: model.set_visible(rulers, True))
            _ = menu.addAction("Hide", lambda: model.set_visible(rulers, False))
            menu.addSeparator()
            _ = menu.addAction(
                "Remove rulers", lambda: self._remove_rulers(rulers)
            )

        viewport = self.viewport()
        if viewport is None:
            return
        menu.exec(viewport.mapToGlobal(position))
