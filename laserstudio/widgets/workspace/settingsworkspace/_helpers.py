"""Small UI helper functions and slider row primitives used across panels."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from laserstudio.instruments.camera import CameraInstrument
from laserstudio.widgets.newui import theme
from laserstudio.widgets.workspace.schemaform import _INPUT_SS

from ._styles import _FIELD_CONTROL_H, _MONO_DIM, _MONO_MUTED, _SLIDER_ROW_H


def _compact_panel(layout: QVBoxLayout) -> None:
    """Absorb spare vertical space at the bottom so controls stay packed at the
    top and never spread apart, whatever height the panel is given."""
    layout.addStretch(1)


def _sidebar_btn(btn: QPushButton) -> QPushButton:
    btn.setFixedHeight(theme.BTN_MIN_H)
    btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return btn


def _format_coords(coords: list[float]) -> str:
    parts = [f"{v:+.1f}" for v in coords[:3]]
    while len(parts) < 3:
        parts.append("+0.0")
    return ", ".join(parts)


def pixel_size_um(camera: CameraInstrument) -> float:
    return float(camera.pixel_size_in_um[0]) / camera.objective


# ── Small UI helpers ───────────────────────────────────────────────────────────


def _mono_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(_MONO_MUTED)
    return lbl


def _value_box(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {theme.TEXT}; font-family: monospace; font-size: 11px;"
        f" background: {theme.BG_CARD}; border: 1px solid {theme.BORDER};"
        " border-radius: 5px; padding: 5px 10px;"
    )
    lbl.setFixedHeight(_FIELD_CONTROL_H)
    lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    return lbl


def _readout_field(text: str) -> QLineEdit:
    field = QLineEdit(text)
    field.setReadOnly(True)
    field.setStyleSheet(_INPUT_SS)
    field.setFixedHeight(_FIELD_CONTROL_H)
    return field


def _param_grid_cell(label: str, control: QWidget) -> QWidget:
    cell = QWidget()
    cell.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(cell)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(_mono_label(label))
    control.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    layout.addWidget(control)
    return cell


def _two_col_param_grid(cells: list[tuple[str, QWidget]]) -> QWidget:
    wrap = QWidget()
    wrap.setStyleSheet("background: transparent;")
    grid = QGridLayout(wrap)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(0)
    for col, (label, control) in enumerate(cells):
        grid.addWidget(_param_grid_cell(label, control), 0, col)
        grid.setColumnStretch(col, 1)
    return wrap


def _step_field(
    label: str, value: float, step: float, on_change: Callable[[float], None]
) -> tuple[QWidget, QDoubleSpinBox]:
    field = QWidget()
    field.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(field)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(_mono_label(label))
    spin = QDoubleSpinBox()
    spin.setStyleSheet(_INPUT_SS)
    spin.setFixedHeight(_FIELD_CONTROL_H)
    spin.setMinimum(0)
    spin.setMaximum(1_000_000)
    spin.setDecimals(1)
    spin.setSingleStep(step)
    spin.setSuffix("\xa0µm")
    spin.setValue(value)
    spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    spin.valueChanged.connect(on_change)
    layout.addWidget(spin)
    return field, spin


class _SliderRow(QWidget):
    """Labelled slider with a live value readout."""

    def __init__(
        self,
        caption: str,
        minimum: int,
        maximum: int,
        value: int,
        fmt: Callable[[int], str],
        on_change: Callable[[int], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fmt = fmt
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self._caption = QLabel(caption)
        self._caption.setStyleSheet(_MONO_MUTED)
        self._value = QLabel(fmt(value))
        self._value.setStyleSheet(
            f"color: {theme.TEXT}; font-family: monospace; font-size: 10px;"
            " background: transparent;"
        )
        header.addWidget(self._caption)
        header.addStretch()
        header.addWidget(self._value)
        layout.addLayout(header)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(minimum, maximum)
        self._slider.setValue(value)
        self._slider.setStyleSheet(
            "QSlider::groove:horizontal { height: 4px; background: #1E1E1E;"
            " border-radius: 2px; }"
            f"QSlider::sub-page:horizontal {{ background: {theme.PURPLE};"
            " border-radius: 2px; }"
            "QSlider::handle:horizontal { width: 12px; margin: -4px 0;"
            f" background: {theme.PURPLE}; border-radius: 6px; }}"
        )
        self._slider.valueChanged.connect(self._on_changed)
        self._on_change = on_change
        layout.addWidget(self._slider)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(_SLIDER_ROW_H)

    def _on_changed(self, val: int) -> None:
        self._value.setText(self._fmt(val))
        self._on_change(val)

    def set_value(self, val: int) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(val)
        self._value.setText(self._fmt(val))
        self._slider.blockSignals(False)

    def setEnabled(self, a0: bool) -> None:
        super().setEnabled(a0)
        self._slider.setEnabled(a0)


class _FloatSliderRow(QWidget):
    """Labelled slider for a floating-point range, with a live value readout."""

    def __init__(
        self,
        caption: str,
        minimum: float,
        maximum: float,
        value: float,
        *,
        scale: int = 1000,
        suffix: str = "",
        decimals: int = 3,
        on_change: Callable[[float], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._scale = scale
        self._decimals = decimals
        self._suffix = suffix
        self._on_change = on_change
        self._minimum = minimum
        self._maximum = maximum

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self._caption = QLabel(caption)
        self._caption.setStyleSheet(_MONO_MUTED)
        self._value = QLabel(self._format(value))
        self._value.setStyleSheet(
            f"color: {theme.TEXT}; font-family: monospace; font-size: 10px;"
            " background: transparent;"
        )
        header.addWidget(self._caption)
        header.addStretch()
        header.addWidget(self._value)
        layout.addLayout(header)

        slider_min = int(round(minimum * scale))
        slider_max = max(slider_min + 1, int(round(maximum * scale)))
        slider_val = min(slider_max, max(slider_min, int(round(value * scale))))

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(slider_min, slider_max)
        self._slider.setValue(slider_val)
        self._slider.setStyleSheet(
            "QSlider::groove:horizontal { height: 4px; background: #1E1E1E;"
            " border-radius: 2px; }"
            f"QSlider::sub-page:horizontal {{ background: {theme.PURPLE};"
            " border-radius: 2px; }"
            "QSlider::handle:horizontal { width: 12px; margin: -4px 0;"
            f" background: {theme.PURPLE}; border-radius: 6px; }}"
        )
        self._slider.valueChanged.connect(self._on_changed)
        layout.addWidget(self._slider)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(_SLIDER_ROW_H)

    def _format(self, value: float) -> str:
        return f"{value:.{self._decimals}f}{self._suffix}"

    def _on_changed(self, raw: int) -> None:
        value = raw / self._scale
        value = min(self._maximum, max(self._minimum, value))
        self._value.setText(self._format(value))
        self._on_change(value)

    def set_value(self, value: float) -> None:
        raw = int(round(min(self._maximum, max(self._minimum, value)) * self._scale))
        self._slider.blockSignals(True)
        self._slider.setValue(raw)
        self._value.setText(self._format(value))
        self._slider.blockSignals(False)
