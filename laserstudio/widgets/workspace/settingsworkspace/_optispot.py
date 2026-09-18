"""Single-axis optispot stage: slider, +/- nudges, and a numeric position field."""

from __future__ import annotations

import logging
import math

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from laserstudio.instruments.stage import StageInstrument, Vector
from laserstudio.widgets.newui import theme
from laserstudio.widgets.optispotcontrol import OPTISPOT_MAX, OPTISPOT_MIN, OPTISPOT_STEP
from laserstudio.widgets.return_line_edit import ReturnDoubleSpinBox
from laserstudio.widgets.workspace.schemaform import _INPUT_SS

from ._styles import _DPAN_BTN, _FIELD_CONTROL_H, _MONO_MUTED


class _OptispotSection(QWidget):
    """Single-axis optispot stage: slider, +/- nudges, and a numeric position field."""

    def __init__(
        self, optispot: StageInstrument, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._optispot = optispot
        self._last_position = float(OPTISPOT_MIN)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        caption = QLabel("OPTISPOT")
        caption.setStyleSheet(_MONO_MUTED)
        header.addWidget(caption)
        header.addStretch()
        self._spin = ReturnDoubleSpinBox()
        self._spin.setStyleSheet(_INPUT_SS)
        self._spin.setFixedHeight(_FIELD_CONTROL_H)
        self._spin.setMinimum(float(OPTISPOT_MIN))
        self._spin.setMaximum(float(OPTISPOT_MAX))
        self._spin.setDecimals(1)
        self._spin.setSingleStep(float(OPTISPOT_STEP))
        self._spin.setKeyboardTracking(False)
        self._spin.setToolTip(
            "Optispot position. Press Enter or use the arrows to apply."
        )
        self._spin.setFixedWidth(96)
        self._spin.valueChanged.connect(self._on_spin_changed)
        header.addWidget(self._spin)
        root.addLayout(header)

        controls = QWidget()
        controls.setStyleSheet("background: transparent;")
        row = QHBoxLayout(controls)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        minus = QPushButton("−")
        minus.setToolTip("Decrease optispot position")
        minus.setStyleSheet(_DPAN_BTN)
        minus.setFixedSize(QSize(32, 28))
        minus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        minus.clicked.connect(lambda: self._nudge(-OPTISPOT_STEP))
        row.addWidget(minus)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(OPTISPOT_MIN, OPTISPOT_MAX)
        self._slider.setValue(OPTISPOT_MIN)
        self._slider.setToolTip("Optispot position")
        self._slider.setStyleSheet(
            "QSlider::groove:horizontal { height: 4px; background: #1E1E1E;"
            " border-radius: 2px; }"
            f"QSlider::sub-page:horizontal {{ background: {theme.PURPLE};"
            " border-radius: 2px; }"
            "QSlider::handle:horizontal { width: 12px; margin: -4px 0;"
            f" background: {theme.PURPLE}; border-radius: 6px; }}"
        )
        self._slider.valueChanged.connect(self._on_slider_changed)
        row.addWidget(self._slider, 1)

        plus = QPushButton("+")
        plus.setToolTip("Increase optispot position")
        plus.setStyleSheet(_DPAN_BTN)
        plus.setFixedSize(QSize(32, 28))
        plus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        plus.clicked.connect(lambda: self._nudge(OPTISPOT_STEP))
        row.addWidget(plus)
        root.addWidget(controls)

        optispot.position_changed.connect(self._on_position_changed)
        try:
            self._on_position_changed(optispot.position)
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to read the optispot position: {exc}"
            )

    def _spin_is_being_edited(self) -> bool:
        line_edit = self._spin.lineEdit()
        return line_edit is not None and line_edit.hasFocus()

    def _on_position_changed(self, position: Vector) -> None:
        x = float(position.x)
        if math.isnan(x):
            # An unreadable position must not be used as the base for +/-.
            return
        self._last_position = x
        clamped = max(float(OPTISPOT_MIN), min(float(OPTISPOT_MAX), x))
        if not self._spin_is_being_edited():
            self._spin.blockSignals(True)
            self._spin.setValue(clamped)
            self._spin.reset()
            self._spin.blockSignals(False)
        if self._slider.isSliderDown():
            return
        self._slider.blockSignals(True)
        self._slider.setValue(round(clamped))
        self._slider.blockSignals(False)

    def _on_slider_changed(self, value: int) -> None:
        self._move_to(float(value))

    def _on_spin_changed(self, value: float) -> None:
        self._move_to(value)

    def _nudge(self, delta: float) -> None:
        self._move_to(self._last_position + delta)

    def _move_to(self, value: float) -> None:
        value = max(float(OPTISPOT_MIN), min(float(OPTISPOT_MAX), value))
        try:
            self._optispot.move_to(Vector(value), wait=False)
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to move the optispot: {exc}"
            )
