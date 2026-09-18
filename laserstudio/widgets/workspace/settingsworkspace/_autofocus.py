"""Autofocus: register an unbounded number of focused points, and apply
autofocus at the current position once it falls inside a Delaunay triangle
of at least 3 registered points."""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from laserstudio.instruments.focus import FocusInstrument
from laserstudio.instruments.stage import StageInstrument, Vector
from laserstudio.widgets.newui import lucide, theme

from ._styles import PANEL_SPACING, _TRASH_BTN_SS


class _AutofocusSection(QWidget):
    """Register focus points and apply autofocus once the current position
    is covered by the triangulation of at least 3 registered points."""

    def __init__(self, window: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self._stage: StageInstrument = window.instruments.stage
        self._focus_helper: FocusInstrument = window.instruments.focus_helper
        self._row_widgets: list[QWidget] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(PANEL_SPACING)

        root.addWidget(theme.section_title("Autofocus", "scan-eye"))
        root.addWidget(
            self._hint(
                "Register the current position at several focused spots, then "
                "apply autofocus anywhere: it interpolates inside the triangle "
                "they form, or extrapolates from the nearest one outside it. "
                "Register more points to cover a wider area precisely."
            )
        )

        register_row = QHBoxLayout()
        register_row.setSpacing(8)
        register_btn = QPushButton("Register current position")
        register_btn.setStyleSheet(theme.GHOST_BTN)
        register_btn.setIcon(lucide.icon("crosshair", 14, theme.TEXT))
        register_btn.clicked.connect(self._on_register)
        register_row.addWidget(register_btn, 1)
        self._count_lbl = QLabel("0 points")
        self._count_lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-family: monospace; font-size: 10px;"
            " background: transparent;"
        )
        register_row.addWidget(self._count_lbl)
        root.addLayout(register_row)

        self._rows_container = QWidget()
        self._rows_container.setStyleSheet("background: transparent;")
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(4)
        root.addWidget(self._rows_container)

        clear_btn = QPushButton("Clear all registered points")
        clear_btn.setStyleSheet(theme.GHOST_BTN)
        clear_btn.setIcon(lucide.icon("trash-2", 14, theme.TEXT_DIM))
        clear_btn.clicked.connect(self._focus_helper.clear)
        root.addWidget(clear_btn)

        root.addWidget(theme.separator())

        self._coverage_lbl = QLabel("—")
        self._coverage_lbl.setWordWrap(True)
        self._coverage_lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; background: transparent;"
        )
        root.addWidget(self._coverage_lbl)

        self._apply_btn = QPushButton("Apply autofocus")
        self._apply_btn.setStyleSheet(theme.GHOST_BTN)
        self._apply_btn.setIcon(lucide.icon("scan-eye", 14, theme.TEXT))
        self._apply_btn.clicked.connect(self._on_apply)
        root.addWidget(self._apply_btn)

        self._focus_helper.parameter_changed.connect(self._on_param)
        self._stage.position_changed.connect(self._on_position_changed)

        self._rebuild_rows()
        self._refresh_coverage(self._stage.position)

    # ── construction helpers ──────────────────────────────────────────────────
    def _hint(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; background: transparent;"
        )
        return lbl

    def _row(self, index: int, x: float, y: float, z: float) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(f"X {x:+.2f}  Y {y:+.2f}  Z {z:+.2f} µm")
        label.setStyleSheet(
            f"color: {theme.TEXT}; font-family: monospace; font-size: 10px;"
            f" background: {theme.BG_CARD}; border: 1px solid {theme.BORDER};"
            " border-radius: 5px; padding: 5px 8px;"
        )
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(label, 1)

        trash = QPushButton()
        trash.setObjectName("ls-ref-trash")
        trash.setFixedSize(28, theme.BTN_MIN_H)
        trash.setIcon(lucide.icon("trash-2", 13, theme.TEXT_DIM))
        trash.setToolTip("Remove this point")
        trash.setStyleSheet(_TRASH_BTN_SS)
        trash.clicked.connect(lambda: self._focus_helper.remove_point(index))
        layout.addWidget(trash)
        return row

    # ── model → UI ──────────────────────────────────────────────────────────
    def _on_param(self, parameter: str, value: object) -> None:
        if parameter != "autofocus_points":
            return
        self._rebuild_rows()
        self._refresh_coverage(self._stage.position)

    def _on_position_changed(self, position: Vector) -> None:
        self._refresh_coverage(position)

    def _rebuild_rows(self) -> None:
        for row in self._row_widgets:
            self._rows_layout.removeWidget(row)
            row.deleteLater()
        self._row_widgets.clear()

        points = self._focus_helper.autofocus_helper.registered_points
        self._count_lbl.setText(f"{len(points)} point{'s' if len(points) != 1 else ''}")
        for index, (x, y, z) in enumerate(points):
            row = self._row(index, x, y, z)
            self._rows_layout.addWidget(row)
            self._row_widgets.append(row)

    def _refresh_coverage(self, position: Vector) -> None:
        available = self._focus_helper.can_autofocus_at(position.x, position.y)
        self._apply_btn.setEnabled(available)
        num_points = len(self._focus_helper.autofocus_helper)
        if not available:
            self._coverage_lbl.setText(
                f"Register at least 3 (non-aligned) points to enable autofocus "
                f"({num_points} registered)."
            )
        elif self._focus_helper.is_autofocus_exact_at(position.x, position.y):
            self._coverage_lbl.setText("Current position is covered — autofocus available.")
        else:
            self._coverage_lbl.setText(
                "Current position is outside the registered coverage area — "
                "autofocus will extrapolate from the nearest registered triangle."
            )

    # ── UI → model ──────────────────────────────────────────────────────────
    def _on_register(self) -> None:
        self._focus_helper.register()

    def _on_apply(self) -> None:
        try:
            self._focus_helper.autofocus()
        except Exception as exc:
            logging.getLogger("laserstudio").warning(f"Autofocus failed: {exc}")
