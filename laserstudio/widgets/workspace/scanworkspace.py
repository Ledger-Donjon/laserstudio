"""Scan workspace — scan zone list and scan controls."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PyQt6 import sip
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction, QColor, QIcon, QMouseEvent, QCursor
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...utils.colors import MARKERS_COLORS, ZONE_COLORS
from ...utils.scanzones import ScanZone
from ...instruments.scans import ScansInstrument
from ...utils.util import colored_image, create_color_qicon
from ..newui import lucide, theme
from ..return_line_edit import ReturnDoubleSpinBox, ReturnSpinBox
from ..viewer import Viewer
from .schemaform import ToggleSwitch
from .settingsworkspace import _two_col_param_grid
from .workspace import Workspace

if TYPE_CHECKING:
    from ...laserstudio_refonte import LaserStudioRefonte


def _row_style(zone_color: str, active: bool) -> str:
    """Stylesheet for one zone row.

    The active zone is the one every drawing gesture lands in, so it is marked
    unmistakably rather than subtly: a thick left bar in the zone's own color,
    a lifted background and an accented border. Inactive rows keep a
    transparent bar of the same width so nothing shifts when the selection
    moves.
    """
    if active:
        return f"""
QFrame#ls-zone-row {{
    background: {theme.PURPLE_BG};
    border: 1px solid {theme.PURPLE_BORDER};
    border-left: 4px solid {zone_color};
    border-radius: 8px;
}}
"""
    return f"""
QFrame#ls-zone-row {{
    background: {theme.BG_CARD};
    border: 1px solid {theme.BORDER_SUBTLE};
    border-left: 4px solid transparent;
    border-radius: 8px;
}}
QFrame#ls-zone-row:hover {{
    border-color: {theme.BORDER_HOVER};
}}
"""


_NAME_SS = f"""
QLineEdit {{
    background: transparent;
    border: none;
    color: {theme.TEXT};
    font-size: 12px;
    padding: 0;
}}
QLineEdit:focus {{
    border-bottom: 1px solid {theme.BORDER_HOVER};
}}
"""

_ICON_BTN_SS = f"""
QPushButton {{
    background: transparent;
    border: 1px solid {theme.BORDER_SUBTLE};
    border-radius: 6px;
    padding: 3px;
}}
QPushButton:hover {{
    border-color: {theme.BORDER_HOVER};
}}
"""


class _ZoneRow(QFrame):
    """One row of the zone list.

    Holds the :class:`ScanZone` it renders, so ``_pending_rename`` and
    ``_restore_focus`` can find a row by zone identity rather than by
    position: a concurrent model change may reorder the list mid-rename.
    """

    def __init__(self, zone: ScanZone, on_activate: Callable[[], None]):
        super().__init__()
        self.zone = zone
        self._on_activate = on_activate

    def mousePressEvent(self, a0: QMouseEvent | None) -> None:  # noqa: N802 (Qt override)
        """Clicking the row — but not one of its controls, which get the
        event first — makes this zone the active one."""
        self._on_activate()
        if a0 is not None:
            a0.accept()

    def name_edit(self) -> QLineEdit | None:
        """:return: This row's name editor, or None if the row has no layout."""
        row_layout = self.layout()
        if row_layout is None or row_layout.count() < 2:
            return None
        item = row_layout.itemAt(1)
        widget = item.widget() if item is not None else None
        return widget if isinstance(widget, QLineEdit) else None


class ScanWorkspace(Workspace):
    """Left panel of the Scan tab: the zone list, then the scan controls."""

    label = "Scan"
    icon = "scan"

    def __init__(self, viewer: Viewer, scans: ScansInstrument) -> None:
        super().__init__()
        self._rows_layout: QVBoxLayout | None = None
        self._syncing = False

        self._mode_buttons: QButtonGroup | None = None
        self._density: ReturnSpinBox | None = None
        self._point_size: ReturnDoubleSpinBox | None = None
        self._path_color: QComboBox | None = None

        self.viewer = viewer
        self.zones = scans

        self.zones.zone_changed.connect(self._on_changed)
        self.zones.path_changed.connect(self._on_path_changed)
        self.zones.active_zone_changed.connect(self._on_active_zone_changed)

    # ── Panel ────────────────────────────────────────────────────────────────

    def build_panel(self) -> QWidget:
        scroll = theme.setup_scroll_area(QScrollArea())
        inner = theme.panel_inner()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(theme.eyebrow("WORKSPACE · SCAN"))
        layout.addWidget(theme.section_title("Zones", "scan"))

        rows = QWidget()
        rows.setStyleSheet("background: transparent;")
        self._rows_layout = QVBoxLayout(rows)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(8)
        layout.addWidget(rows)

        add = QPushButton("Add zone")
        add.setIcon(lucide.icon("plus", 14, theme.TEXT))
        add.setCursor(Qt.CursorShape.PointingHandCursor)
        add.clicked.connect(self._on_add_zone)
        layout.addWidget(add)

        layout.addWidget(theme.separator())
        layout.addWidget(theme.section_title("Draw", "spline"))
        layout.addWidget(self._draw_section())

        layout.addWidget(theme.separator())
        layout.addWidget(theme.section_title("Scan", "crosshair"))
        layout.addWidget(self._scan_section())

        layout.addWidget(theme.separator())
        layout.addWidget(theme.section_title("Path", "activity"))
        layout.addWidget(self._path_section())

        layout.addStretch(1)
        scroll.setWidget(inner)

        self._sync_rows()
        self._sync_scan_controls()
        return scroll

    def _on_changed(self) -> None:
        self._sync_rows()
        self._sync_scan_controls()

    def _on_path_changed(self) -> None:
        self._sync_scan_controls()

    def _on_active_zone_changed(self, zone_id: int) -> None:
        self._sync_rows()

    # ── Zone list ────────────────────────────────────────────────────────────

    def _on_add_zone(self) -> None:
        zone = self.zones.add_zone()
        self._on_activate(zone)

    def _pending_rename(self, layout: QVBoxLayout) -> tuple[ScanZone, str] | None:
        """Detect an in-progress, uncommitted rename in one of the rows.

        If a row's name editor currently has focus and holds text that
        differs from its zone's name (the user is still typing —
        ``editingFinished`` hasn't fired), return ``(zone, typed_text)``.
        The zone *object* is returned (not its row index) because the index
        recorded when the row was built can be stale by the time this runs:
        this is only ever consulted from ``_sync_rows``, i.e. in reaction to
        a model change that may itself have inserted/removed/reordered
        zones since these rows were laid out.
        """
        for i in range(layout.count()):
            item = layout.itemAt(i)
            row = item.widget() if item is not None else None
            if not isinstance(row, _ZoneRow):
                continue
            name_edit = row.name_edit()
            if name_edit is None or not name_edit.hasFocus():
                continue
            text = name_edit.text()
            if text and text != row.zone.name:
                return row.zone, text
        return None

    def _restore_focus(self, index: int, zone: ScanZone) -> None:
        """Refocus the name editor of the row that was just rebuilt for
        ``zone`` at ``index``, cursor at the end — undoing the focus loss
        that rebuilding rows would otherwise cause mid-rename."""
        layout = self._rows_layout
        if layout is None or sip.isdeleted(layout):
            return
        if not (0 <= index < layout.count()):
            return
        item = layout.itemAt(index)
        row = item.widget() if item is not None else None
        if not isinstance(row, _ZoneRow) or row.zone is not zone:
            return
        name_edit = row.name_edit()
        if name_edit is not None:
            name_edit.setFocus(Qt.FocusReason.OtherFocusReason)
            name_edit.end(False)

    def _sync_rows(self) -> None:
        """Rebuild the zone rows from the model."""
        if self._syncing:
            return
        layout = self._rows_layout
        if layout is None or sip.isdeleted(layout):
            return

        zones = self.zones

        # Preserve an in-progress rename: an unrelated model change (a REST
        # call, the classic toolbar, a drag committing a geometry elsewhere)
        # must not silently discard text the user hasn't committed yet.
        pending = self._pending_rename(layout)
        if pending is not None and zones is not None:
            zone, text = pending
            try:
                zone = zones.zone(zone.id)
            except KeyError:
                zone = None  # the zone was removed by whatever change we
                # are reacting to; nothing sensible left to commit.
            if zone is not None:
                try:
                    zones.update_zone(zone)
                except KeyError:
                    zone = None
                else:
                    # update_zone() above synchronously re-emitted `changed`,
                    # which re-entered this method (self._syncing was still
                    # False) and already rebuilt the rows with both the
                    # external change and this rename applied.
                    self._restore_focus(zone.id, zone)
                    return

        self._syncing = True
        try:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget() if item is not None else None
                if widget is not None:
                    widget.setParent(None)

            if zones is None or not zones.zones:
                empty = QLabel("No zone yet — draw one, or add it here.")
                empty.setStyleSheet(
                    f"color: {theme.TEXT_DIM}; font-size: 11px;"
                    " background: transparent;"
                )
                empty.setWordWrap(True)
                layout.addWidget(empty)
                return

            for zone in zones.zones.values():
                layout.addWidget(self._zone_row(zone, zone == zones.active_zone))
        finally:
            self._syncing = False

    def _zone_row(self, zone: ScanZone, active: bool) -> QWidget:
        row = _ZoneRow(zone, lambda: self._on_activate(zone))
        row.setObjectName("ls-zone-row")
        row.setProperty("active", "true" if active else "false")
        row.setStyleSheet(_row_style(zone.color.name(), active))
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setToolTip(
            "Active zone — drawing adds to this one"
            if active
            else "Click to make this the active zone"
        )

        hl = QHBoxLayout(row)
        hl.setContentsMargins(10, 8, 10, 8)
        hl.setSpacing(9)

        swatch = QPushButton()
        swatch.setStyleSheet(_ICON_BTN_SS)
        swatch.setIcon(create_color_qicon(zone.color))
        swatch.setFixedSize(26, 24)
        swatch.setToolTip("Zone color")
        swatch.setCursor(Qt.CursorShape.PointingHandCursor)
        swatch.clicked.connect(lambda _checked, z=zone: self._pick_color(z))
        hl.addWidget(swatch)

        name = QLineEdit(zone.name)
        # The active zone's name is bold, one of several cues marking it.
        name.setStyleSheet(
            _NAME_SS + ("QLineEdit { font-weight: 700; }" if active else "")
        )
        name.setToolTip("Zone name")
        name.editingFinished.connect(
            lambda z=zone, w=name: self._on_rename(z, w.text())
        )
        hl.addWidget(name, stretch=1)

        toggle = ToggleSwitch(zone.enabled)
        toggle.setToolTip("Include this zone in the scan")
        toggle.toggled.connect(lambda on, z=zone: self._on_toggle(z, on))
        hl.addWidget(toggle)

        delete = QPushButton()
        delete.setStyleSheet(_ICON_BTN_SS)
        delete.setIcon(lucide.icon("trash-2", 14, theme.TEXT_MUTED))
        delete.setFixedSize(26, 24)
        delete.setToolTip("Delete this zone")
        delete.setCursor(Qt.CursorShape.PointingHandCursor)
        delete.clicked.connect(lambda _checked, z=zone: self._on_delete(z))
        hl.addWidget(delete)

        return row

    def _on_activate(self, zone: ScanZone) -> None:
        if self.zones is not None and zone in self.zones.zones.values():
            self.zones.active_zone = zone

    def _on_rename(self, zone: ScanZone, text: str) -> None:
        if self._syncing or self.zones is None or zone not in self.zones.zones.values():
            return
        if text and text != zone.name:
            zone.name = text
            self.zones.update_zone(zone)

    def _on_toggle(self, zone: ScanZone, enabled: bool) -> None:
        if self.zones is None or self._syncing or zone not in self.zones.zones.values():
            return
        zone.enabled = enabled
        self.zones.update_zone(zone)

    def _on_delete(self, zone: ScanZone) -> None:
        if self.zones is None or self._syncing or zone not in self.zones.zones.values():
            return
        self.zones.remove_zone(zone)

    def _pick_color(self, zone: ScanZone) -> None:
        if self.zones is None or zone not in self.zones.zones.values():
            return
        menu = QMenu()
        for color, name in ZONE_COLORS:
            action = QAction(create_color_qicon(color), name, menu)
            action.triggered.connect(
                lambda _checked, c=color, z=zone: self._set_color(z, c)
            )
            menu.addAction(action)
        menu.exec(QCursor.pos())
        return

    def _set_color(self, zone: ScanZone, color) -> None:
        if self.zones is None or zone not in self.zones.zones.values():
            return
        zone.color = color
        self.zones.update_zone(zone)

    # ── Draw / Scan / Path sections ──────────────────────────────────────────

    def _draw_section(self) -> QWidget:
        """Zone drawing mode buttons, mirroring the classic toolbar."""
        box = QWidget()
        box.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(box)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(6)

        self._mode_buttons = QButtonGroup(box)
        self._mode_buttons.setExclusive(True)

        modes = [
            ("Rectangle", ":/icons/region_rect.svg", Viewer.Mode.ZONE),
            ("Tilted", ":/icons/region_tilted.svg", Viewer.Mode.ZONE_TILTED),
            ("Polygon", ":/icons/region_poly.svg", Viewer.Mode.ZONE_POLY),
        ]
        for text, icon_path, mode in modes:
            btn = QPushButton(f"  {text}")
            # colored_image takes a QColor, not a CSS string like theme.TEXT.
            btn.setIcon(QIcon(colored_image(icon_path, QColor(theme.TEXT))))
            btn.setIconSize(QSize(16, 16))
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(
                f"Draw a {text.lower()} zone. Hold Shift to subtract from the "
                "active zone."
            )
            btn.clicked.connect(lambda _checked, m=mode: self._select_mode(m))
            self._mode_buttons.addButton(btn)
            hl.addWidget(btn)
        return box

    def _select_mode(self, mode: Viewer.Mode) -> None:
        self.viewer.select_mode(mode, toggle=True)

    def _scan_section(self) -> QWidget:
        box = QWidget()
        box.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(box)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(8)

        go = QPushButton("Go to next point")
        go.setIcon(lucide.icon("locate-fixed", 14, theme.TEXT))
        go.setCursor(Qt.CursorShape.PointingHandCursor)
        go.setToolTip("Move the stage to the next generated scan point")
        go.clicked.connect(self._on_go_next)
        vl.addWidget(go)

        zones = self.zones

        self._density = ReturnSpinBox()
        self._density.setMinimum(1)
        self._density.setMaximum(1000)
        self._density.setValue(zones.density if zones is not None else 100)
        self._density.setToolTip(
            "Scan density. The bigger it is, the smaller average distance "
            "between consecutive points is."
        )
        self._density.returnPressed2.connect(self._on_density)
        self._density.reset()

        self._point_size = ReturnDoubleSpinBox()
        self._point_size.setSuffix("\xa0µm")
        self._point_size.setMinimum(0.1)
        self._point_size.setMaximum(2000.0)
        self._point_size.setDecimals(1)
        self._point_size.setSingleStep(1.0)
        self._point_size.setValue(zones.point_diameter if zones is not None else 10.0)
        self._point_size.setToolTip("Size of the points in the scan path")
        self._point_size.returnPressed2.connect(self._on_point_size)
        self._point_size.reset()

        vl.addWidget(
            _two_col_param_grid(
                [("Density", self._density), ("Point size", self._point_size)]
            )
        )
        return box

    def _on_go_next(self) -> None:
        self.viewer.go_next()

    def _on_density(self) -> None:
        zones = self.zones
        widget = self._density
        # A queued signal can still arrive after the panel was torn down, when
        # the widget's C++ side is already gone; then this is a no-op.
        if zones is not None and widget is not None and not sip.isdeleted(widget):
            zones.density = widget.value()

    def _on_point_size(self) -> None:
        zones = self.zones
        widget = self._point_size
        if zones is not None and widget is not None and not sip.isdeleted(widget):
            zones.point_diameter = widget.value()

    def _path_section(self) -> QWidget:
        box = QWidget()
        box.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(box)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(9)

        label = QLabel("Path color")
        label.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px; background: transparent;"
        )
        hl.addWidget(label)
        hl.addStretch(1)

        self._path_color = QComboBox()
        self._path_color.setToolTip("Color of the scan path points")
        for color, name in MARKERS_COLORS:
            self._path_color.addItem(create_color_qicon(color), name, color)
        self._path_color.currentIndexChanged.connect(self._on_path_color)
        hl.addWidget(self._path_color)
        return box

    def _on_path_color(self) -> None:
        zones = self.zones
        combo = self._path_color
        if zones is not None and combo is not None and not sip.isdeleted(combo):
            zones.path_color = QColor(combo.currentData())

    def _sync_scan_controls(self) -> None:
        """Push density / point size / path color from the model into the
        matching widgets.

        Connected to both ``changed`` (path color, point diameter) and
        ``path_changed`` (density) so any writer of the shared model — this
        panel, the classic toolbar, or the REST API — keeps these readouts
        current instead of silently going stale. Every write is wrapped in
        ``blockSignals`` so this can never itself write back into the model.
        """
        layout = self._rows_layout
        if layout is None or sip.isdeleted(layout):
            return
        zones = self.zones
        if zones is None:
            return

        density = self._density
        if density is not None and not sip.isdeleted(density):
            density.blockSignals(True)
            try:
                density.setValue(zones.density)
            finally:
                density.blockSignals(False)

        point_size = self._point_size
        if point_size is not None and not sip.isdeleted(point_size):
            point_size.blockSignals(True)
            try:
                point_size.setValue(zones.point_diameter)
            finally:
                point_size.blockSignals(False)

        combo = self._path_color
        if combo is not None and not sip.isdeleted(combo):
            target = QColor(zones.path_color)
            match = -1
            for i in range(combo.count()):
                if QColor(combo.itemData(i)) == target:
                    match = i
                    break
            if match != -1:
                combo.blockSignals(True)
                try:
                    combo.setCurrentIndex(match)
                finally:
                    combo.blockSignals(False)
            # else: the model's color isn't one of the offered swatches —
            # leave the combo as it is rather than forcing index 0.
