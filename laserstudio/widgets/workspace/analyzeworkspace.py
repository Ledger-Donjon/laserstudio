"""Analyze workspace — measurement annotations (rulers) over the viewer."""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...utils.colors import LedgerColors, MARKERS_COLORS
from ...utils.util import create_color_qicon
from ..newui import theme
from ..rulerslist import RulersView
from ..viewer import Viewer
from .workspace import Workspace

PANEL_SPACING = 12

_RULER_BTN = f"""
QPushButton#ls-ruler-btn {{
    background-color: rgba(255,255,255,0.05);
    color: {theme.TEXT};
    border: 1px solid {theme.BORDER};
    border-radius: 5px;
    font-family: "Brut Grotesque";
    font-size: 12px;
    padding: 6px 12px;
    text-align: left;
}}
QPushButton#ls-ruler-btn:hover {{
    background-color: rgba(255,255,255,0.09);
}}
QPushButton#ls-ruler-btn:checked {{
    background-color: {theme.PURPLE_BG};
    color: {theme.PURPLE};
    border: 1px solid {theme.PURPLE_BORDER};
}}
"""

_LIST_SS = f"""
QTreeView {{
    background: {theme.BG_CARD};
    color: {theme.TEXT};
    border: 1px solid {theme.BORDER};
    border-radius: 5px;
    font-size: 11px;
}}
QTreeView::item {{
    padding: 2px;
}}
QTreeView::item:selected {{
    background: {theme.PURPLE_BG};
    color: {theme.PURPLE};
}}
QHeaderView::section {{
    background: transparent;
    color: {theme.TEXT_DIM};
    border: none;
    border-bottom: 1px solid {theme.BORDER};
    padding: 4px;
    font-size: 10px;
}}
"""


def _field_row(label_text: str, control: QWidget) -> QWidget:
    row = QWidget()
    row.setStyleSheet("background: transparent;")
    hbox = QHBoxLayout(row)
    hbox.setContentsMargins(0, 0, 0, 0)
    hbox.setSpacing(10)
    label = QLabel(label_text)
    label.setStyleSheet(
        f"color: {theme.TEXT_MUTED}; font-size: 12px; background: transparent;"
    )
    hbox.addWidget(label)
    hbox.addStretch()
    control.setFixedHeight(theme.CONTROL_MIN_H)
    hbox.addWidget(control)
    return row


class AnalyzeWorkspace(Workspace):
    """Workspace holding the ruler tool and the list of measurements."""

    label = "Analyze"
    icon = "activity"

    def __init__(self, window: Any) -> None:
        self._window = window
        self._ruler_btn: QPushButton | None = None
        self._color_btn: QPushButton | None = None

    def build_panel(self) -> QWidget:
        scroll = theme.setup_scroll_area(QScrollArea())
        inner = theme.panel_inner()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(PANEL_SPACING)
        layout.addWidget(theme.eyebrow("WORKSPACE · ANALYZE"))
        layout.addWidget(theme.section_title("Measurements", "ruler"))

        viewer: Viewer | None = self._window.viewer
        if viewer is None:
            note = QLabel("No viewer available")
            note.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px;")
            note.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(note)
            layout.addStretch(1)
            scroll.setWidget(inner)
            return scroll

        self._ruler_btn = btn = QPushButton("Ruler")
        btn.setObjectName("ls-ruler-btn")
        btn.setCheckable(True)
        btn.setStyleSheet(_RULER_BTN)
        btn.setFixedHeight(theme.BTN_MIN_H)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setToolTip(
            "Measure a distance by dragging in the viewer. "
            "Shortcut: L — leave with Esc."
        )
        btn.toggled.connect(self._on_ruler_toggled)
        viewer.mode_changed.connect(self._on_viewer_mode_changed)
        layout.addWidget(btn)

        self._color_btn = color_btn = QPushButton()
        color_btn.setStyleSheet(theme.GHOST_BTN)
        color_btn.setToolTip("Color for new rulers")
        color_menu = QMenu(color_btn)
        for color, name in MARKERS_COLORS:

            def on_pick(
                _checked: bool = False, *, c: QColor | Qt.GlobalColor | int = color
            ) -> None:
                self._set_color(c)

            color_menu.addAction(create_color_qicon(color), name, on_pick)
        color_btn.setMenu(color_menu)
        layout.addWidget(_field_row("Color", color_btn))
        self._set_color(viewer.default_ruler_color)

        graduation = QDoubleSpinBox()
        graduation.setSuffix("\xa0µm")
        graduation.setToolTip(
            "Graduation interval for new rulers (0 draws a plain line)."
        )
        graduation.setDecimals(1)
        graduation.setSingleStep(10.0)
        graduation.setRange(0.0, 1e6)
        graduation.setValue(viewer.default_ruler_graduation or 0.0)
        graduation.valueChanged.connect(self._on_graduation_changed)
        layout.addWidget(_field_row("Graduation", graduation))

        rulers_list = RulersView(viewer)
        rulers_list.setStyleSheet(_LIST_SS)
        rulers_list.setMinimumHeight(160)
        rulers_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(rulers_list, 1)

        clear_btn = QPushButton("Clear all")
        clear_btn.setStyleSheet(theme.GHOST_BTN)
        clear_btn.setFixedHeight(theme.BTN_MIN_H)
        clear_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        clear_btn.clicked.connect(viewer.clear_rulers)
        layout.addWidget(clear_btn)

        self._on_viewer_mode_changed(int(viewer.mode))
        scroll.setWidget(inner)
        return scroll

    def on_deactivated(self) -> None:
        """Leave the ruler mode, so a click in another workspace does not draw."""
        viewer: Viewer | None = self._window.viewer
        if viewer is not None and viewer.mode == Viewer.Mode.RULER:
            viewer.select_mode(Viewer.Mode.NONE)

    def _on_ruler_toggled(self, checked: bool) -> None:
        viewer: Viewer | None = self._window.viewer
        if viewer is None:
            return
        viewer.select_mode(Viewer.Mode.RULER if checked else Viewer.Mode.NONE)

    def _on_viewer_mode_changed(self, mode_id: int) -> None:
        btn = self._ruler_btn
        if btn is None:
            return
        btn.blockSignals(True)
        btn.setChecked(mode_id == int(Viewer.Mode.RULER))
        btn.blockSignals(False)

    def _set_color(self, color: QColor | Qt.GlobalColor | int | LedgerColors) -> None:
        viewer: Viewer | None = self._window.viewer
        if isinstance(color, LedgerColors):
            color = color.value
        if viewer is not None:
            viewer.default_ruler_color = QColor(color)
        if self._color_btn is not None:
            self._color_btn.setIcon(create_color_qicon(color))

    def _on_graduation_changed(self, value: float) -> None:
        viewer: Viewer | None = self._window.viewer
        if viewer is not None:
            viewer.default_ruler_graduation = value if value > 0 else None
