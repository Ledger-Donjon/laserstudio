"""Settings workspace — sub-category panels (camera, positioning, focus, …)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QEvent, QObject, QSize, Qt, QTimer
from PyQt6.QtGui import QFocusEvent, QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...instruments.camera import CameraInstrument
from ...instruments.camera_nit import CameraNITInstrument
from ...instruments.camera_raptor import CameraRaptorInstrument
from ...instruments.camera_usb import CameraUSBInstrument
from ...instruments.shutter import ShutterInstrument
from ...instruments.stage import StageInstrument, Vector
from ..keyboardbox import Direction, arrow_key_direction, direction_axis
from ..newui import lucide, theme
from ..return_line_edit import ReturnDoubleSpinBox, ReturnSpinBox
from ..viewer import Viewer
from .schemaform import ToggleSwitch, _INPUT_SS
from .workspace import Workspace

# PDM lasers are optional (require the pypdm driver); import defensively so the
# whole Settings UI still loads if the driver is unavailable.
try:
    from ...instruments.pdm import PDMInstrument, InterlockStatus
except Exception:  # pragma: no cover - pypdm is an optional dependency
    PDMInstrument = None  # type: ignore[assignment,misc]
    InterlockStatus = None  # type: ignore[assignment,misc]

# Fixed tabs header + scrollable sub-panel content; see build_panel.
_DPAD_CELL = 44
_DPAD_GAP = 6
_DPAD_MIN_WIDTH = _DPAD_CELL * 3 + _DPAD_GAP * 2
_ICONS_DIR = Path(__file__).resolve().parents[2] / "icons"

# ── Styles ─────────────────────────────────────────────────────────────────────

_DPAN_BTN = f"""
QPushButton {{
    background: rgba(255,255,255,0.05);
    color: {theme.TEXT};
    border: 1px solid {theme.BORDER};
    border-radius: 5px;
    min-height: 40px;
    padding: 0;
}}
QPushButton:hover {{ background: rgba(255,255,255,0.09); }}
QPushButton:pressed {{ padding-top: 1px; }}
QPushButton:disabled {{
    color: {theme.TEXT_DIM};
    background: rgba(255,255,255,0.02);
    border-color: rgba(255,255,255,0.06);
}}
"""

_Z_BTN = f"""
QPushButton {{
    background: {theme.PURPLE_BG};
    color: {theme.PURPLE};
    border: 1px solid {theme.PURPLE_BORDER};
    border-radius: 5px;
    font-family: monospace;
    font-size: 11px;
    min-height: 40px;
    padding: 0;
}}
QPushButton:hover {{ background: rgba(212,160,255,0.20); }}
QPushButton:pressed {{ padding-top: 1px; }}
"""

# Scoped under #ls-sub-bar so the global ledger QPushButton:checked (orange) does not win.
_SUB_BAR_SS = f"""
QWidget#ls-sub-bar QPushButton {{
    background-color: transparent;
    color: {theme.TAB_INACTIVE};
    border: 1px solid {theme.BORDER_SUBTLE};
    border-radius: 5px;
    font-family: "Brut Grotesque";
    font-size: 11px;
    font-weight: 700;
    text-align: left;
    padding: 6px 10px;
    min-height: 0;
}}
QWidget#ls-sub-bar QPushButton:hover {{
    color: {theme.TEXT};
    background-color: rgba(255,255,255,0.05);
}}
QWidget#ls-sub-bar QPushButton:checked {{
    background-color: {theme.PURPLE_BG};
    color: {theme.PURPLE};
    border: 1px solid {theme.PURPLE_BORDER};
}}
QWidget#ls-sub-bar QPushButton:checked:hover {{
    background-color: rgba(212,160,255,0.18);
    color: {theme.PURPLE};
    border-color: rgba(212,160,255,0.50);
}}
"""

_CLICK_MOVE_BTN = f"""
QPushButton#ls-click-move-btn {{
    background-color: rgba(255,255,255,0.05);
    color: {theme.TEXT};
    border: 1px solid {theme.BORDER};
    border-radius: 5px;
    font-family: "Brut Grotesque";
    font-size: 12px;
    padding: 6px 12px;
    text-align: left;
}}
QPushButton#ls-click-move-btn:hover {{
    background-color: rgba(255,255,255,0.09);
}}
QPushButton#ls-click-move-btn:checked {{
    background-color: {theme.PURPLE_BG};
    color: {theme.PURPLE};
    border: 1px solid {theme.PURPLE_BORDER};
}}
"""

# Shutter Open/Closed — separate toggles (design), not a single pill.
_SHUTTER_OPEN = theme.GREEN
_SHUTTER_OPEN_BG = theme.GREEN_BG
_SHUTTER_OPEN_BORDER = "rgba(110,200,92,0.40)"
_SHUTTER_CLOSED = theme.ACCENT
_SHUTTER_CLOSED_BG = "rgba(255,83,0,0.12)"
_SHUTTER_CLOSED_BORDER = "rgba(255,83,0,0.40)"

# Laser ARM button — subtle accent when safe, filled accent when armed.
_LASER_ARM_SAFE_SS = f"""
QPushButton {{
    background: rgba(255,83,0,0.10);
    color: {theme.ACCENT};
    border: 1px solid rgba(255,83,0,0.50);
    border-radius: 5px;
    font-family: "Brut Grotesque";
    font-weight: 700;
    font-size: 12px;
    padding: 6px 14px;
    min-height: 0;
    max-height: {theme.BTN_MIN_H}px;
}}
QPushButton:hover {{ background: rgba(255,83,0,0.18); }}
"""
_LASER_ARM_ARMED_SS = f"""
QPushButton {{
    background: {theme.ACCENT};
    color: #0A0A0A;
    border: 1px solid {theme.ACCENT};
    border-radius: 5px;
    font-family: "Brut Grotesque";
    font-weight: 700;
    font-size: 12px;
    padding: 6px 14px;
    min-height: 0;
    max-height: {theme.BTN_MIN_H}px;
}}
QPushButton:hover {{ background: #FF6A26; }}
"""

# Segmented control (design): a rounded container holding two borderless
# buttons that fill with a tint when active.
_SHUTTER_BTN_SS = f"""
QWidget#ls-shutter-row {{
    background-color: {theme.BG_CARD};
    border: 1px solid {theme.BORDER};
    border-radius: 6px;
}}
QWidget#ls-shutter-row QPushButton {{
    background-color: transparent;
    color: {theme.TEXT_MUTED};
    border: none;
    border-radius: 4px;
    font-family: "Brut Grotesque";
    font-weight: 700;
    font-size: 11px;
    padding: 6px 12px;
    min-height: 0;
    max-height: {theme.CONTROL_MIN_H}px;
}}
QWidget#ls-shutter-row QPushButton:hover {{
    background-color: rgba(255,255,255,0.05);
    color: {theme.TEXT};
}}
QWidget#ls-shutter-row QPushButton#ls-shutter-open:checked {{
    background-color: {_SHUTTER_OPEN_BG};
    color: {_SHUTTER_OPEN};
}}
QWidget#ls-shutter-row QPushButton#ls-shutter-closed:checked {{
    background-color: {_SHUTTER_CLOSED_BG};
    color: {_SHUTTER_CLOSED};
}}
"""

_TRASH_BTN_SS = f"""
QPushButton#ls-ref-trash {{
    background: rgba(255,255,255,0.05);
    border: 1px solid {theme.BORDER};
    border-radius: 5px;
    padding: 0;
}}
QPushButton#ls-ref-trash:hover {{
    color: #F04F52;
    border-color: rgba(240,79,82,0.4);
    background: rgba(240,79,82,0.08);
}}
QPushButton#ls-ref-trash:disabled {{
    color: {theme.TEXT_DIM};
    border-color: rgba(255,255,255,0.06);
    background: rgba(255,255,255,0.02);
}}
"""

_DIST_SET_BTN = f"""
QPushButton#ls-dist-set {{
    background: {theme.PURPLE_BG};
    color: {theme.PURPLE};
    border: 1px solid {theme.PURPLE_BORDER};
    border-radius: 5px;
    font-family: "Brut Grotesque";
    font-size: 11px;
    padding: 0 12px;
    min-height: 0;
    max-height: {theme.BTN_MIN_H}px;
}}
QPushButton#ls-dist-set:hover {{
    background: rgba(212,160,255,0.20);
}}
QPushButton#ls-dist-set:disabled {{
    color: {theme.TEXT_DIM};
    background: rgba(255,255,255,0.02);
    border-color: rgba(255,255,255,0.06);
}}
"""

PANEL_SPACING = 12
_SLIDER_ROW_H = 38


def _compact_panel(layout: QVBoxLayout) -> None:
    """Absorb spare vertical space at the bottom so controls stay packed at the
    top and never spread apart, whatever height the panel is given."""
    layout.addStretch(1)


def _sidebar_btn(btn: QPushButton) -> QPushButton:
    btn.setFixedHeight(theme.BTN_MIN_H)
    btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return btn


_FIELD_CONTROL_H = theme.CONTROL_MIN_H

_MONO_DIM = (
    f"color: {theme.TEXT_DIM}; font-family: monospace; font-size: 10px;"
    " background: transparent;"
)
_MONO_MUTED = (
    f"color: {theme.TEXT_MUTED}; font-family: monospace; font-size: 10px;"
    " background: transparent;"
)


def _format_coords(coords: list[float]) -> str:
    parts = [f"{v:+.1f}" for v in coords[:3]]
    while len(parts) < 3:
        parts.append("+0.0")
    return ", ".join(parts)


def available_objectives(camera: CameraInstrument) -> list[float]:
    """Magnifications offered for this camera type (matches classic dock widgets)."""
    if isinstance(camera, CameraRaptorInstrument):
        return [10.0, 20.0]
    if isinstance(camera, CameraNITInstrument):
        return [5.0, 10.0, 20.0, 50.0]
    return [1.0, 5.0, 10.0, 20.0, 50.0]


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

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        super().setEnabled(enabled)
        self._slider.setEnabled(enabled)


class _ShutterSection(QWidget):
    """Shutter heading (with live status) + Open / Closed toggles."""

    def __init__(
        self, shutter: ShutterInstrument, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._shutter = shutter

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        header = QWidget()
        header.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(9)
        icon = QLabel()
        icon.setPixmap(lucide.pixmap("aperture", 16, theme.PURPLE))
        icon.setFixedWidth(20)
        icon.setStyleSheet("background: transparent;")
        header_layout.addWidget(icon)
        title = QLabel("Shutter")
        title.setStyleSheet(
            f"color: {theme.TEXT}; font-family: 'Brut Grotesque'; font-weight: 700;"
            " font-size: 15px; background: transparent;"
        )
        header_layout.addWidget(title)
        header_layout.addStretch()
        self._status_lbl = QLabel()
        self._status_lbl.setStyleSheet(
            f"font-family: monospace; font-size: 10px; letter-spacing: 1px;"
            " background: transparent;"
        )
        header_layout.addWidget(self._status_lbl)
        root.addWidget(header)

        row = QWidget()
        row.setObjectName("ls-shutter-row")
        row.setStyleSheet(_SHUTTER_BTN_SS)
        btn_layout = QHBoxLayout(row)
        btn_layout.setContentsMargins(3, 3, 3, 3)
        btn_layout.setSpacing(6)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        btn_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._open_btn = QPushButton("Open")
        self._open_btn.setObjectName("ls-shutter-open")
        self._open_btn.setCheckable(True)
        self._open_btn.setIconSize(QSize(13, 13))
        self._open_btn.setFixedHeight(_FIELD_CONTROL_H)
        self._open_btn.setSizePolicy(btn_policy)

        self._closed_btn = QPushButton("Closed")
        self._closed_btn.setObjectName("ls-shutter-closed")
        self._closed_btn.setCheckable(True)
        self._closed_btn.setIconSize(QSize(13, 13))
        self._closed_btn.setFixedHeight(_FIELD_CONTROL_H)
        self._closed_btn.setSizePolicy(btn_policy)

        self._group.addButton(self._open_btn)
        self._group.addButton(self._closed_btn)
        self._open_btn.clicked.connect(lambda: self._apply(True))
        self._closed_btn.clicked.connect(lambda: self._apply(False))
        btn_layout.addWidget(self._open_btn)
        btn_layout.addWidget(self._closed_btn)
        root.addWidget(row)

        self._sync_ui()

    def _apply(self, open_state: bool) -> None:
        if self._shutter.open != open_state:
            self._shutter.open = open_state
        self._sync_ui()

    def _sync_ui(self) -> None:
        open_state = self._shutter.open
        for btn, checked in (
            (self._open_btn, open_state),
            (self._closed_btn, not open_state),
        ):
            btn.blockSignals(True)
            btn.setChecked(checked)
            btn.blockSignals(False)
        # Icons follow the active state color (green open / orange closed),
        # muted otherwise — matching the button text color like the design.
        self._open_btn.setIcon(
            lucide.icon(
                "circle-dot",
                13,
                _SHUTTER_OPEN if open_state else theme.TEXT_MUTED,
            )
        )
        self._closed_btn.setIcon(
            lucide.icon(
                "circle",
                13,
                _SHUTTER_CLOSED if not open_state else theme.TEXT_MUTED,
            )
        )
        if open_state:
            self._status_lbl.setText("OPEN")
            self._status_lbl.setStyleSheet(
                f"color: {_SHUTTER_OPEN}; font-family: monospace; font-size: 10px;"
                " letter-spacing: 1px; background: transparent;"
            )
        else:
            self._status_lbl.setText("CLOSED")
            self._status_lbl.setStyleSheet(
                f"color: {_SHUTTER_CLOSED}; font-family: monospace; font-size: 10px;"
                " letter-spacing: 1px; background: transparent;"
            )


class _LaserSection(QWidget):
    """Controls for one laser: ARM (on/off), pulse power, offset current,
    pulse width and delay, plus read-only interlock status and temperature.

    Behaviour mirrors the classic PDM dock (``PDMDockWidget``): editable numeric
    values are applied on Enter (not on every keystroke) to avoid flooding the
    device, and the widgets track the instrument via ``parameter_changed``.
    Sweep controls are intentionally omitted for now.
    """

    def __init__(self, laser: Any, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._laser = laser
        self._is_pdm = PDMInstrument is not None and isinstance(laser, PDMInstrument)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(PANEL_SPACING)

        # Header: zap icon + name + driver tag.
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        head = QHBoxLayout(header)
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(9)
        icon = QLabel()
        icon.setPixmap(lucide.pixmap("zap", 16, theme.PURPLE))
        icon.setFixedWidth(20)
        icon.setStyleSheet("background: transparent;")
        head.addWidget(icon)
        title = QLabel(laser.label or f"Laser {index + 1}")
        title.setStyleSheet(
            f"color: {theme.TEXT}; font-family: 'Brut Grotesque'; font-weight: 700;"
            " font-size: 15px; background: transparent;"
        )
        head.addWidget(title)
        head.addStretch()
        driver = type(laser).__name__.replace("Instrument", "").upper()
        driver_lbl = QLabel(driver)
        driver_lbl.setStyleSheet(_MONO_DIM)
        head.addWidget(driver_lbl)
        root.addWidget(header)

        if not self._is_pdm:
            note = QLabel("This laser type is managed in the classic interface.")
            note.setWordWrap(True)
            note.setStyleSheet(
                f"color: {theme.TEXT_DIM}; font-size: 11px; background: transparent;"
            )
            root.addWidget(note)
            return

        # ARM status + toggle (the on/off of the classic UI).
        arm_row = QWidget()
        arm_row.setStyleSheet("background: transparent;")
        arm_layout = QHBoxLayout(arm_row)
        arm_layout.setContentsMargins(0, 0, 0, 0)
        arm_layout.setSpacing(9)
        self._arm_status = QLabel("ARM · SAFE")
        arm_layout.addWidget(self._arm_status)
        arm_layout.addStretch()
        self._arm_btn = QPushButton("ARM")
        self._arm_btn.setCheckable(True)
        self._arm_btn.setIconSize(QSize(14, 14))
        self._arm_btn.setToolTip("Arm / disarm the laser (ON / OFF)")
        self._arm_btn.clicked.connect(self._on_arm_clicked)
        arm_layout.addWidget(self._arm_btn)
        root.addWidget(arm_row)

        # Interlock status (read-only).
        self._interlock_val = QLabel("—")
        root.addWidget(self._status_card("INTERLOCK", self._interlock_val))

        # Pulse power (%) + offset current (mA).
        self._power_spin = self._double_field(0.0, 100.0, 2, "\xa0%")
        self._power_spin.returnPressed2.connect(
            lambda: self._apply("current_percentage", self._power_spin.value())
        )
        self._offset_spin = self._double_field(0.0, 150.0, 3, "\xa0mA")
        self._offset_spin.returnPressed2.connect(
            lambda: self._apply("offset_current", self._offset_spin.value())
        )
        root.addWidget(
            _two_col_param_grid(
                [
                    ("PULSE POWER", self._power_spin),
                    ("OFFSET CURRENT", self._offset_spin),
                ]
            )
        )

        # Pulse width (ps) + delay (ps).
        self._pw_spin = self._int_field(0, 1275000, "\xa0ps")
        self._pw_spin.returnPressed2.connect(
            lambda: self._apply("pulse_width", self._pw_spin.value())
        )
        self._delay_spin = self._int_field(0, 15000, "\xa0ps")
        self._delay_spin.returnPressed2.connect(
            lambda: self._apply("delay", self._delay_spin.value())
        )
        root.addWidget(
            _two_col_param_grid(
                [
                    ("PULSE WIDTH", self._pw_spin),
                    ("DELAY", self._delay_spin),
                ]
            )
        )

        # Temperature (read-only).
        self._temp_field = _readout_field("—")
        root.addWidget(_param_grid_cell("TEMPERATURE", self._temp_field))

        hint = QLabel("Numeric values are applied when you press Enter.")
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; background: transparent;"
        )
        root.addWidget(hint)

        laser.parameter_changed.connect(self._on_param)
        self._refresh_all()

    # ── construction helpers ──────────────────────────────────────────────────
    def _status_card(self, label: str, value_lbl: QLabel) -> QWidget:
        card = QWidget()
        card.setFixedHeight(theme.BTN_MIN_H)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        card.setStyleSheet(
            f"background: {theme.BG_CARD}; border: 1px solid {theme.BORDER};"
            " border-radius: 5px;"
        )
        lay = QHBoxLayout(card)
        lay.setContentsMargins(10, 0, 10, 0)
        key = QLabel(label)
        key.setStyleSheet(_MONO_MUTED)
        lay.addWidget(key)
        lay.addStretch()
        value_lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-family: monospace; font-size: 11px;"
            " background: transparent;"
        )
        lay.addWidget(value_lbl)
        return card

    def _double_field(
        self, minimum: float, maximum: float, decimals: int, suffix: str
    ) -> ReturnDoubleSpinBox:
        spin = ReturnDoubleSpinBox()
        spin.setStyleSheet(_INPUT_SS)
        spin.setFixedHeight(_FIELD_CONTROL_H)
        spin.setMinimum(minimum)
        spin.setMaximum(maximum)
        spin.setDecimals(decimals)
        spin.setSuffix(suffix)
        spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return spin

    def _int_field(self, minimum: int, maximum: int, suffix: str) -> ReturnSpinBox:
        spin = ReturnSpinBox()
        spin.setStyleSheet(_INPUT_SS)
        spin.setFixedHeight(_FIELD_CONTROL_H)
        spin.setMinimum(minimum)
        spin.setMaximum(maximum)
        spin.setSuffix(suffix)
        spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return spin

    # ── device interaction ────────────────────────────────────────────────────
    def _apply(self, attr: str, value: float) -> None:
        try:
            setattr(self._laser, attr, value)
        except Exception as exc:  # keep the UI responsive on device errors
            logging.getLogger("laserstudio").warning(
                f"Failed to set laser {attr}: {exc}"
            )

    def _on_arm_clicked(self) -> None:
        try:
            self._laser.on_off = self._arm_btn.isChecked()
        except Exception as exc:
            logging.getLogger("laserstudio").warning(f"Failed to toggle laser: {exc}")
        self._sync_arm()

    def _sync_arm(self, on: bool | None = None) -> None:
        if on is None:
            on = bool(self._arm_btn.isChecked())
        self._arm_btn.blockSignals(True)
        self._arm_btn.setChecked(on)
        self._arm_btn.blockSignals(False)
        self._arm_btn.setText("ARMED" if on else "ARM")
        self._arm_btn.setStyleSheet(_LASER_ARM_ARMED_SS if on else _LASER_ARM_SAFE_SS)
        self._arm_btn.setIcon(lucide.icon("zap", 14, "#0A0A0A" if on else theme.ACCENT))
        self._arm_status.setText(f"ARM · {'ARMED' if on else 'SAFE'}")
        self._arm_status.setStyleSheet(
            f"color: {theme.ACCENT if on else theme.GREEN};"
            " font-family: monospace; font-size: 10px; letter-spacing: 1px;"
            " background: transparent;"
        )

    def _set_interlock(self, status: Any) -> None:
        is_open = InterlockStatus is not None and status == InterlockStatus.OPEN
        self._interlock_val.setText("OPEN" if is_open else "CLOSED")
        self._interlock_val.setStyleSheet(
            f"color: {theme.ACCENT if is_open else theme.GREEN};"
            " font-family: monospace; font-size: 11px; background: transparent;"
        )
        self._interlock_val.setToolTip("Laser safety interlock loop status")

    def _set_spin(self, spin: ReturnDoubleSpinBox | ReturnSpinBox, value: Any) -> None:
        if value is None:
            return
        spin.blockSignals(True)
        spin.setValue(value)
        spin.blockSignals(False)
        spin.reset()

    def _refresh_temperature(self) -> None:
        try:
            self._temp_field.setText(f"{self._laser.temperature:.2f}\xa0°C")
        except Exception:
            pass

    def _on_param(self, name: str, value: Any) -> None:
        if name == "on_off":
            self._sync_arm(bool(value))
        elif name == "current_percentage":
            self._set_spin(self._power_spin, value)
        elif name == "offset_current":
            self._set_spin(self._offset_spin, value)
        elif name == "pulse_width":
            self._set_spin(self._pw_spin, value)
        elif name == "delay":
            self._set_spin(self._delay_spin, value)
        elif name == "interlock_status":
            self._set_interlock(value)
        # Temperature has no dedicated signal; refresh it opportunistically.
        self._refresh_temperature()

    def _refresh_all(self) -> None:
        def safe(getter: Callable[[], Any]) -> Any:
            try:
                return getter()
            except Exception:
                return None

        laser = self._laser
        on = safe(lambda: laser.on_off)
        self._sync_arm(bool(on) if on is not None else False)
        self._set_spin(self._power_spin, safe(lambda: laser.current_percentage))
        self._set_spin(self._offset_spin, safe(lambda: laser.offset_current))
        self._set_spin(self._pw_spin, safe(lambda: laser.pulse_width))
        self._set_spin(self._delay_spin, safe(lambda: laser.delay))
        interlock = safe(lambda: laser.interlock_status)
        if interlock is not None:
            self._set_interlock(interlock)
        self._refresh_temperature()


class _SubPanelStack(QStackedWidget):
    """Stack whose height follows the visible panel, not the tallest one."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:  # type: ignore[override]
        current = self.currentWidget()
        if current is not None:
            return current.sizeHint()
        return super().sizeHint()

    def minimumSizeHint(self) -> QSize:  # type: ignore[override]
        current = self.currentWidget()
        if current is not None:
            return current.minimumSizeHint()
        return super().minimumSizeHint()

    def setCurrentIndex(self, index: int) -> None:
        super().setCurrentIndex(index)
        self.updateGeometry()
        parent = self.parentWidget()
        if parent is not None:
            parent.updateGeometry()


class SubCategoryBar(QWidget):
    """2-column grid of sub-category tabs (Camera / Positioning / …)."""

    _COLS = 2

    def __init__(
        self,
        tabs: list[tuple[str, str, str]],
        on_select: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ls-sub-bar")
        self.setStyleSheet(_SUB_BAR_SS)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        for c in range(self._COLS):
            grid.setColumnStretch(c, 1)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for i, (key, label, icon_name) in enumerate(tabs):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("ls_key", key)
            btn.setProperty("ls_icon", icon_name)
            btn.setIcon(lucide.icon(icon_name, 14, theme.TAB_INACTIVE))
            btn.setIconSize(QSize(14, 14))
            btn.setToolTip(label)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _c=False, k=key: on_select(k))
            self._group.addButton(btn)
            grid.addWidget(btn, i // self._COLS, i % self._COLS)

    def select(self, key: str) -> None:
        for btn in self._group.buttons():
            active = btn.property("ls_key") == key
            btn.setChecked(active)
            icon = str(btn.property("ls_icon"))
            btn.setIcon(
                lucide.icon(icon, 14, theme.PURPLE if active else theme.TAB_INACTIVE)
            )


def _keyboard_toggle_button(parent: QWidget) -> QPushButton:
    """Small keyboard-control toggle button for a D-pad (bottom-right corner)."""
    btn = QPushButton(parent)
    btn.setIcon(lucide.icon("keyboard", 14, theme.TEXT_DIM))
    btn.setFixedSize(22, 22)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    # Must not steal focus from the D-pad (which needs it to receive key events).
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setToolTip(
        "Keyboard control: click, then move with the arrow keys "
        "(Z with Page Up / Page Down). Shift ×10, Ctrl ×0.1."
    )
    btn.setStyleSheet(
        f"QPushButton {{ background: {theme.BG_CARD}; border: 1px solid"
        f" {theme.BORDER}; border-radius: 5px; }}"
        f" QPushButton:hover {{ border-color: {theme.PURPLE}; }}"
    )
    return btn


class DpadWidget(QWidget):
    """3×3 positioning pad wired to a stage instrument."""

    def __init__(
        self,
        stage: StageInstrument,
        *,
        include_home: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._stage = stage
        self._include_home = include_home
        self._num_axis = stage.num_axis
        self._displacement_xy = 100.0
        self._displacement_z = 10.0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        pad = QWidget()
        pad.setStyleSheet("background: transparent;")
        # +2 keeps a 1px margin around the grid so the outermost buttons'
        # borders are never clipped at the pad's edge.
        pad.setFixedWidth(_DPAD_MIN_WIDTH + 2)
        grid = QGridLayout(pad)
        grid.setContentsMargins(1, 1, 1, 1)
        grid.setHorizontalSpacing(_DPAD_GAP)
        grid.setVerticalSpacing(_DPAD_GAP)

        btn_policy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn_size = QSize(_DPAD_CELL, 40)

        if self._num_axis > 1:
            grid.addWidget(self._arrow_btn("arrow-up", Direction.up), 0, 1)
        if self._num_axis > 0:
            grid.addWidget(self._arrow_btn("arrow-left", Direction.left), 1, 0)
            if self._include_home:
                grid.addWidget(self._home_btn(), 1, 1)
            else:
                spacer = QWidget()
                spacer.setFixedSize(btn_size)
                spacer.setStyleSheet("background: transparent;")
                grid.addWidget(spacer, 1, 1)
            grid.addWidget(self._arrow_btn("arrow-right", Direction.right), 1, 2)
        if self._num_axis > 1:
            grid.addWidget(self._arrow_btn("arrow-down", Direction.down), 2, 1)
        if self._num_axis > 2:
            grid.addWidget(self._z_btn("Z+", Direction.zup), 0, 2)
            grid.addWidget(self._z_btn("Z−", Direction.zdown), 2, 2)

        for i in range(grid.count()):
            item = grid.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, QPushButton):
                widget.setFixedSize(btn_size)
                widget.setSizePolicy(btn_policy)

        # Keyboard control toggle, anchored to the bottom-right of the pad.
        self._pad = pad
        self._kbd_btn = _keyboard_toggle_button(pad)
        self._kbd_btn.clicked.connect(self._toggle_keyboard)
        pad.installEventFilter(self)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        QTimer.singleShot(0, self._reposition_keyboard_button)

        pad_wrap = QHBoxLayout()
        pad_wrap.setContentsMargins(0, 0, 0, 0)
        pad_wrap.addStretch()
        pad_wrap.addWidget(pad)
        pad_wrap.addStretch()
        root.addLayout(pad_wrap)

        if self._num_axis > 0:
            xy_field, self._xy_spin = _step_field(
                "STEP X/Y", self._displacement_xy, 5.0, self._on_xy_step_changed
            )
            root.addWidget(xy_field)
        if self._num_axis > 2:
            z_field, self._z_spin = _step_field(
                "STEP Z", self._displacement_z, 10.0, self._on_z_step_changed
            )
            root.addWidget(z_field)

    def _on_xy_step_changed(self, value: float) -> None:
        self._displacement_xy = value

    def _on_z_step_changed(self, value: float) -> None:
        self._displacement_z = value

    def _arrow_btn(self, icon: str, direction: Direction) -> QPushButton:
        btn = QPushButton()
        btn.setIcon(lucide.icon(icon, 16, theme.TEXT))
        btn.setStyleSheet(_DPAN_BTN)
        btn.clicked.connect(lambda: self._move(direction))
        return btn

    def _z_btn(self, label: str, direction: Direction) -> QPushButton:
        btn = QPushButton(label)
        btn.setStyleSheet(_Z_BTN)
        btn.clicked.connect(lambda: self._move(direction))
        return btn

    def _home_btn(self) -> QPushButton:
        btn = QPushButton()
        btn.setIcon(lucide.icon("home", 16, theme.TEXT_DIM))
        btn.setStyleSheet(_DPAN_BTN)
        btn.setEnabled(self._num_axis > 0)
        btn.clicked.connect(self._go_origin)
        return btn

    def _go_origin(self) -> None:
        self._stage.move_to(Vector(*([0.0] * self._num_axis)), wait=False)

    def _move(self, direction: Direction) -> None:
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            factor = 10.0
        elif modifiers & Qt.KeyboardModifier.ControlModifier:
            factor = 0.1
        else:
            factor = 1.0

        if direction in (Direction.left, Direction.right):
            axe = 0
        elif direction in (Direction.up, Direction.down):
            axe = 1
        elif direction in (Direction.zup, Direction.zdown):
            axe = 2
        else:
            return

        displacement = self._displacement_z if axe == 2 else self._displacement_xy
        if direction in (Direction.down, Direction.left, Direction.zdown):
            displacement *= -1
        displacement *= factor

        position = self._stage.position
        position[axe] += displacement
        self._stage.move_to(position, wait=False)

    # ── Keyboard control ────────────────────────────────────────────────────
    def _toggle_keyboard(self) -> None:
        if self.hasFocus():
            self.clearFocus()
        else:
            self.setFocus(Qt.FocusReason.MouseFocusReason)

    def _reposition_keyboard_button(self) -> None:
        btn, pad = self._kbd_btn, self._pad
        btn.move(pad.width() - btn.width(), pad.height() - btn.height())
        btn.raise_()

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:
        if (
            obj is self._pad
            and event is not None
            and event.type() == QEvent.Type.Resize
        ):
            self._reposition_keyboard_button()
        return super().eventFilter(obj, event)

    def _set_keyboard_active(self, active: bool) -> None:
        color = theme.PURPLE if active else theme.TEXT_DIM
        self._kbd_btn.setIcon(lucide.icon("keyboard", 14, color))
        self._pad.setStyleSheet(
            "background: transparent;"
            + (
                f" border: 1px solid {theme.PURPLE}; border-radius: 6px;"
                if active
                else ""
            )
        )
        self._reposition_keyboard_button()

    def focusInEvent(self, a0: QFocusEvent | None) -> None:
        super().focusInEvent(a0)
        self._set_keyboard_active(True)

    def focusOutEvent(self, a0: QFocusEvent | None) -> None:
        super().focusOutEvent(a0)
        self._set_keyboard_active(False)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        direction = arrow_key_direction(a0.key()) if a0 is not None else None
        if direction is not None and direction_axis(direction) < self._num_axis:
            self._move(direction)
            if a0 is not None:
                a0.accept()
            return
        super().keyPressEvent(a0)


class _SafetyLimitsSection(QWidget):
    """Stage safety limits: two independently-toggleable guardrails.

    * **Max move distance**: block any single move whose amplitude exceeds a
      distance (per axis). Maps to :attr:`StageInstrument.guardrail` /
      :attr:`StageInstrument.guardrail_enabled`.
    * **Stage area limit**: confine every move to a rectangular zone, editable
      by dragging the handles of the rectangle in the viewer. Maps to the
      stage software limits (:attr:`StageInstrument.soft_limits_enabled` and the
      soft-limits box).
    """

    def __init__(self, window: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self._stage: StageInstrument = window.instruments.stage
        # Guards against feedback loops while we refresh the widgets from the
        # model (setting a toggle/spin value must not write back to the stage).
        self._updating = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(PANEL_SPACING)

        root.addWidget(theme.section_title("Safety limits", "shield"))

        # ── Max move distance ──────────────────────────────────────────────
        self._distance_toggle = ToggleSwitch(self._stage.guardrail_enabled)
        self._distance_toggle.toggled.connect(self._on_distance_enabled)
        root.addWidget(self._sub_header("Max move distance", self._distance_toggle))
        root.addWidget(self._hint("Block any single move longer than this distance."))
        self._distance_spin = QDoubleSpinBox()
        self._distance_spin.setStyleSheet(_INPUT_SS)
        self._distance_spin.setFixedHeight(_FIELD_CONTROL_H)
        self._distance_spin.setMinimum(0.0)
        self._distance_spin.setMaximum(1_000_000.0)
        self._distance_spin.setDecimals(1)
        self._distance_spin.setSingleStep(1000.0)
        self._distance_spin.setSuffix("\xa0µm")
        self._distance_spin.setValue(self._stage.guardrail)
        self._distance_spin.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._distance_spin.valueChanged.connect(self._on_distance_changed)
        root.addWidget(_param_grid_cell("MAXIMUM DISTANCE", self._distance_spin))

        root.addWidget(theme.separator())

        # ── Stage area limit ───────────────────────────────────────────────
        self._area_toggle = ToggleSwitch(self._stage.soft_limits_enabled)
        self._area_toggle.toggled.connect(self._on_area_enabled)
        root.addWidget(self._sub_header("Stage area limit", self._area_toggle))
        root.addWidget(
            self._hint(
                "Confine every move to a rectangular zone — drag the handles of "
                "the rectangle in the viewer to resize it."
            )
        )
        self._area_bounds = QLabel("—")
        self._area_bounds.setWordWrap(True)
        self._area_bounds.setStyleSheet(
            f"color: {theme.TEXT}; font-family: monospace; font-size: 11px;"
            f" background: {theme.BG_CARD}; border: 1px solid {theme.BORDER};"
            " border-radius: 5px; padding: 8px 10px;"
        )
        self._area_bounds.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        root.addWidget(self._area_bounds)

        self._stage.guardrail_changed.connect(self._refresh_distance)
        self._stage.soft_limits_changed.connect(self._refresh_area)
        self._refresh_distance()
        self._refresh_area()

    # ── construction helpers ───────────────────────────────────────────────
    def _sub_header(self, title: str, toggle: ToggleSwitch) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)
        label = QLabel(title)
        label.setStyleSheet(
            f"color: {theme.TEXT}; font-family: 'Brut Grotesque'; font-weight: 700;"
            " font-size: 13px; background: transparent;"
        )
        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(toggle)
        return row

    def _hint(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; background: transparent;"
        )
        return label

    # ── Max move distance ──────────────────────────────────────────────────
    def _on_distance_enabled(self, on: bool) -> None:
        if self._updating:
            return
        self._stage.guardrail_enabled = on
        viewer = self._window.viewer
        if viewer is not None:
            viewer.set_max_distance_editable(on)

    def _on_distance_changed(self, value: float) -> None:
        if self._updating:
            return
        self._stage.guardrail = float(value)

    def _refresh_distance(self) -> None:
        self._updating = True
        try:
            self._distance_toggle.setChecked(self._stage.guardrail_enabled)
            self._distance_spin.setValue(self._stage.guardrail)
        finally:
            self._updating = False
        viewer = self._window.viewer
        if viewer is not None:
            viewer.set_max_distance_editable(self._stage.guardrail_enabled)

    # ── Stage area limit ───────────────────────────────────────────────────
    def _on_area_enabled(self, on: bool) -> None:
        if self._updating:
            return
        if on and not self._stage.has_soft_limits:
            self._init_default_area()
        self._stage.soft_limits_enabled = on
        viewer = self._window.viewer
        if viewer is not None:
            viewer.set_soft_limits_editable(on)

    def _init_default_area(self) -> None:
        """Create a default area around the visible view / current position."""
        position = self._stage.position.data
        rect = None
        viewer = self._window.viewer
        viewport = viewer.viewport() if viewer is not None else None
        if viewer is not None and viewport is not None:
            rect = viewer.mapToScene(viewport.rect()).boundingRect()
        if rect is not None and rect.width() > 1.0 and rect.height() > 1.0:
            xmin, xmax = rect.left(), rect.right()
            ymin, ymax = rect.top(), rect.bottom()
        else:
            x = position[0] if len(position) > 0 else 0.0
            y = position[1] if len(position) > 1 else 0.0
            xmin, xmax = x - 5000.0, x + 5000.0
            ymin, ymax = y - 5000.0, y + 5000.0
        minimum = [xmin, ymin]
        maximum = [xmax, ymax]
        if self._stage.num_axis >= 3:
            z = position[2] if len(position) > 2 else 0.0
            minimum.append(z - 5000.0)
            maximum.append(z + 5000.0)
        self._stage.set_soft_limits(minimum, maximum)

    def _refresh_area(self) -> None:
        self._updating = True
        try:
            self._area_toggle.setChecked(self._stage.soft_limits_enabled)
            self._area_bounds.setText(self._area_bounds_text())
        finally:
            self._updating = False
        viewer = self._window.viewer
        if viewer is not None:
            viewer.set_soft_limits_editable(self._stage.soft_limits_enabled)

    def _area_bounds_text(self) -> str:
        minimum = self._stage.soft_limits_min
        maximum = self._stage.soft_limits_max
        if minimum is None or maximum is None:
            return "No area defined yet."
        lines = []
        for i, axis in enumerate("XYZ"[: self._stage.num_axis]):
            if i < len(minimum) and i < len(maximum):
                lines.append(f"{axis}: {minimum[i]:g} … {maximum[i]:g} µm")
        return "\n".join(lines) if lines else "No area defined yet."


class SettingsWorkspace(Workspace):
    """Setup workspace with sub-category panels."""

    label = "Settings"
    icon = "move-3d"

    _SUB_TABS: list[tuple[str, str, str]] = [
        ("camera", "Camera", "camera"),
        ("positioning", "Positioning", "move-3d"),
        ("focus", "Focus tools", "scan-eye"),
        ("reference", "Reference", "image"),
    ]

    def __init__(self, window: Any) -> None:
        self._window = window
        self._coord_label: QLabel | None = None
        self._pixel_size_lbl: QLineEdit | None = None
        self._objective_combo: QComboBox | None = None
        self._sub_stack: QStackedWidget | None = None
        self._sub_bar: SubCategoryBar | None = None
        self._sub_keys: list[str] = []
        self._click_move_btn: QPushButton | None = None
        self._ref_opacity: _SliderRow | None = None
        self._ref_trash_btn: QPushButton | None = None
        self._ref_set_dist_btn: QPushButton | None = None
        self._ref_reset_btn: QPushButton | None = None
        self._ref_status_val: QLabel | None = None
        self._ref_cam_status_val: QLabel | None = None
        self._distortion_wired = False

    def build_panel(self) -> QWidget:
        # Fixed header (eyebrow + sub-category tabs) that never scrolls, so the
        # sub-category selection stays visible; only the panel content below
        # lives inside the scroll area.
        root = QWidget()
        root.setObjectName(theme.PANEL_INNER)
        root.setStyleSheet(f"background: {theme.BG_PANEL};")
        root_layout = QVBoxLayout(root)
        # Right margin is slightly smaller — the scroll area's thin scrollbar
        # occupies the remaining edge without clipping panel controls.
        root_layout.setContentsMargins(
            theme.SIDEBAR_MARGIN_H, 18, theme.SIDEBAR_MARGIN_H - 6, 0
        )
        root_layout.setSpacing(PANEL_SPACING)

        root_layout.addWidget(theme.eyebrow("WORKSPACE · SETTINGS"))

        tabs = list(self._SUB_TABS)
        if self._window.instruments.lasers:
            tabs.append(("lasers", "Lasers", "zap"))
        self._sub_keys = [t[0] for t in tabs]

        self._sub_bar = SubCategoryBar(tabs, self._select_sub)
        root_layout.addWidget(self._sub_bar)
        root_layout.addWidget(theme.separator())

        self._sub_stack = _SubPanelStack()
        self._sub_stack.addWidget(self._build_camera_panel())
        self._sub_stack.addWidget(self._build_positioning_panel())
        self._sub_stack.addWidget(self._build_focus_panel())
        self._sub_stack.addWidget(self._build_reference_panel())
        if self._window.instruments.lasers:
            self._sub_stack.addWidget(self._build_lasers_panel())

        # Content wrapper: sub-stack pinned to the top (never stretched
        # vertically), spare height absorbed by a single trailing stretch.
        scroll_content = QWidget()
        scroll_content.setStyleSheet(f"background: {theme.BG_PANEL};")
        sc_layout = QVBoxLayout(scroll_content)
        sc_layout.setContentsMargins(0, 0, 4, 18)
        sc_layout.setSpacing(0)
        sc_layout.addWidget(self._sub_stack, 0, Qt.AlignmentFlag.AlignTop)
        sc_layout.addStretch(1)

        scroll = theme.setup_scroll_area(QScrollArea())
        scroll.setWidget(scroll_content)
        root_layout.addWidget(scroll, 1)

        self._select_sub("camera")
        viewer = self._window.viewer
        if viewer is not None:
            viewer.background_changed.connect(self._sync_reference_panel)
        return root

    def build_content(self) -> QWidget | None:
        return None

    # ── Sub-category switching ────────────────────────────────────────────────

    def _select_sub(self, key: str) -> None:
        if self._sub_bar is not None:
            self._sub_bar.select(key)
        if self._sub_stack is not None and key in self._sub_keys:
            self._sub_stack.setCurrentIndex(self._sub_keys.index(key))
            parent = self._sub_stack.parentWidget()
            if parent is not None:
                parent.updateGeometry()

    # ── Camera panel ────────────────────────────────────────────────────────

    def _build_camera_panel(self) -> QWidget:
        panel = QWidget()
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(PANEL_SPACING)

        layout.addWidget(theme.section_title("Camera parameters", "camera"))

        camera = self._window.instruments.camera
        if camera is None:
            layout.addWidget(self._placeholder("No camera configured"))
            _compact_panel(layout)
            return panel

        # Objective + pixel size — compact 2-column grid (design).
        # Each entry carries a microscope-objective icon whose colored band is
        # the physical magnification ring (kept identical to the classic UI).
        self._objective_combo = combo = QComboBox()
        combo.setStyleSheet(_INPUT_SS)
        combo.setFixedHeight(_FIELD_CONTROL_H)
        combo.setIconSize(QSize(20, 20))
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for mag in available_objectives(camera):
            combo.addItem(lucide.objective_icon(mag, 20), f"{mag:g}×", mag)
            if abs(mag - camera.objective) < 0.01:
                combo.setCurrentIndex(combo.count() - 1)
        combo.currentIndexChanged.connect(self._on_objective_changed)

        self._pixel_size_lbl = _readout_field(f"{pixel_size_um(camera):.1f}\xa0µm")

        layout.addWidget(
            _two_col_param_grid(
                [
                    ("OBJECTIVE", combo),
                    ("PIXEL SIZE", self._pixel_size_lbl),
                ]
            )
        )

        camera.parameter_changed.connect(self._on_camera_parameter_changed)

        # Sliders
        if isinstance(camera, CameraUSBInstrument):
            try:
                layout.addWidget(
                    _SliderRow(
                        "EXPOSURE",
                        0,
                        100,
                        min(100, max(0, int(camera.exposure))),
                        lambda v: f"{v} ms",
                        lambda v: setattr(camera, "exposure", float(v)),
                    )
                )
            except Exception:
                pass
            try:
                layout.addWidget(
                    _SliderRow(
                        "GAIN",
                        0,
                        100,
                        min(100, max(0, int(camera.gain))),
                        lambda v: f"{v:.1f} dB",
                        lambda v: setattr(camera, "gain", float(v)),
                    )
                )
            except Exception:
                pass
            try:
                layout.addWidget(
                    _SliderRow(
                        "BRIGHTNESS",
                        0,
                        255,
                        min(255, max(0, int(camera.brightness))),
                        lambda v: f"{int(v * 100 / 255)} %",
                        lambda v: setattr(camera, "brightness", float(v)),
                    )
                )
            except Exception:
                pass

        # Light
        light = self._window.instruments.light
        if light is not None:
            layout.addWidget(theme.separator())
            dtype = type(light).__name__.replace("Instrument", "")
            layout.addWidget(theme.section_title("Light", "lightbulb"))
            hint = QLabel(dtype.upper())
            hint.setAlignment(Qt.AlignmentFlag.AlignRight)
            hint.setStyleSheet(_MONO_DIM)
            layout.addWidget(
                _SliderRow(
                    "LIGHT LEVEL",
                    0,
                    100,
                    int(light.intensity * 100),
                    lambda v: f"{v} %",
                    lambda v: setattr(light, "intensity", v / 100.0),
                )
            )

        # Shutter
        if camera.shutter is not None:
            layout.addWidget(theme.separator())
            layout.addWidget(_ShutterSection(camera.shutter))

        _compact_panel(layout)
        return panel

    def _on_objective_changed(self, _index: int) -> None:
        camera = self._window.instruments.camera
        combo = self._objective_combo
        if camera is None or combo is None:
            return
        mag = combo.currentData()
        if not isinstance(mag, (float, int)):
            return
        camera.select_objective(float(mag))
        viewer = self._window.viewer
        if viewer is not None and viewer.stage_sight is not None:
            viewer.stage_sight.update_size()
        self._refresh_pixel_size()
        status = getattr(self._window, "_status_bar", None)
        if status is not None:
            status.set_objective(f"{mag:g}×")

    def _on_camera_parameter_changed(self, parameter: str, value: object) -> None:
        if parameter != "objective" or self._objective_combo is None:
            return
        if not isinstance(value, (float, int)):
            return
        combo = self._objective_combo
        combo.blockSignals(True)
        for i in range(combo.count()):
            if abs(float(combo.itemData(i)) - float(value)) < 0.01:
                combo.setCurrentIndex(i)
                break
        combo.blockSignals(False)
        self._refresh_pixel_size()

    def _refresh_pixel_size(self) -> None:
        camera = self._window.instruments.camera
        if camera is None or self._pixel_size_lbl is None:
            return
        self._pixel_size_lbl.setText(f"{pixel_size_um(camera):.1f}\xa0µm")

    # ── Positioning panel ───────────────────────────────────────────────────

    def _build_positioning_panel(self) -> QWidget:
        panel = QWidget()
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(PANEL_SPACING)

        layout.addWidget(theme.section_title("Positioning", "move-3d"))

        viewer = self._window.viewer
        if viewer is not None and viewer.stage_sight is not None:
            self._click_move_btn = btn = QPushButton("Click && Move")
            btn.setObjectName("ls-click-move-btn")
            btn.setCheckable(True)
            btn.setStyleSheet(_CLICK_MOVE_BTN)
            btn.setIcon(lucide.icon("move", 15, theme.TEXT))
            btn.setToolTip(
                "Move the stage to a new position by clicking on the camera view. "
                "Shortcut: M — cancel with Esc."
            )
            btn.toggled.connect(self._on_click_move_toggled)
            viewer.mode_changed.connect(self._on_viewer_mode_changed)
            self._on_viewer_mode_changed(int(viewer.mode))
            layout.addWidget(btn)

        stage = self._window.instruments.stage
        self._coord_label = QLabel("—")
        self._coord_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._coord_label.setStyleSheet(
            f"color: {theme.TEXT};"
            f" background: {theme.BG_CARD}; border: 1px solid {theme.BORDER};"
            " border-radius: 5px; padding: 11px;"
        )
        self._coord_label.setFont(theme.mono_font(14))
        layout.addWidget(self._coord_label)

        if stage is not None:
            layout.addWidget(DpadWidget(stage))
            stage.position_changed.connect(self._on_position_changed)
            self._on_position_changed(stage.position)

            layout.addWidget(theme.separator())
            layout.addWidget(_SafetyLimitsSection(self._window))
        else:
            layout.addWidget(self._placeholder("No stage configured"))

        save_btn = _sidebar_btn(QPushButton("Save memory point"))
        save_btn.setStyleSheet(theme.GHOST_BTN)
        save_btn.clicked.connect(self._save_memory_point)
        layout.addWidget(save_btn)
        _compact_panel(layout)
        return panel

    # ── Focus / Reference / Lasers placeholders ─────────────────────────────

    def _build_focus_panel(self) -> QWidget:
        panel = QWidget()
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(PANEL_SPACING)
        layout.addWidget(theme.section_title("Autofocus", "scan-eye"))
        layout.addWidget(self._placeholder("Autofocus controls — coming soon"))
        layout.addWidget(theme.separator())
        layout.addWidget(theme.section_title("Magic focus", "scan-eye"))
        layout.addWidget(self._placeholder("Magic focus — coming soon"))
        _compact_panel(layout)
        return panel

    def _build_reference_panel(self) -> QWidget:
        panel = QWidget()
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(PANEL_SPACING)
        layout.addWidget(theme.section_title("Reference image", "image"))

        browse_row = QWidget()
        browse_row.setStyleSheet("background: transparent;")
        browse_row.setFixedHeight(theme.BTN_MIN_H)
        browse_row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        browse_layout = QHBoxLayout(browse_row)
        browse_layout.setContentsMargins(0, 0, 0, 0)
        browse_layout.setSpacing(8)

        browse = _sidebar_btn(QPushButton("Browse for reference image…"))
        browse.setStyleSheet(theme.GHOST_BTN)
        browse.setIcon(lucide.icon("folder-open", 14, theme.TEXT_MUTED))
        browse.clicked.connect(self._browse_reference)
        browse_layout.addWidget(browse, stretch=1)

        trash = QPushButton()
        trash.setObjectName("ls-ref-trash")
        trash.setFixedSize(34, theme.BTN_MIN_H)
        trash.setIcon(lucide.icon("trash-2", 14, theme.TEXT_DIM))
        trash.setToolTip("Remove reference image")
        trash.setStyleSheet(_TRASH_BTN_SS)
        trash.clicked.connect(self._clear_reference)
        self._ref_trash_btn = trash
        browse_layout.addWidget(trash)
        layout.addWidget(browse_row)

        viewer = self._window.viewer
        opacity_default = viewer.background_opacity if viewer else 55
        self._ref_opacity = _SliderRow(
            "OPACITY",
            0,
            100,
            opacity_default,
            lambda v: f"{v}%",
            self._on_ref_opacity_changed,
        )
        layout.addWidget(self._ref_opacity)

        layout.addWidget(theme.separator())
        layout.addWidget(theme.section_title("Reference alignment", "move-3d"))

        status_row = QWidget()
        status_row.setFixedHeight(theme.BTN_MIN_H)
        status_row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        status_row.setStyleSheet(
            f"background: {theme.BG_CARD}; border: 1px solid {theme.BORDER};"
            " border-radius: 5px;"
        )
        status_layout = QHBoxLayout(status_row)
        status_layout.setContentsMargins(10, 0, 10, 0)
        key = QLabel("ALIGNMENT")
        key.setStyleSheet(_MONO_MUTED)
        status_layout.addWidget(key)
        status_layout.addStretch()
        self._ref_status_val = QLabel("NONE")
        self._ref_status_val.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-family: monospace; font-size: 11px;"
            " background: transparent;"
        )
        status_layout.addWidget(self._ref_status_val)
        layout.addWidget(status_row)

        dist_row = QWidget()
        dist_row.setFixedHeight(theme.BTN_MIN_H)
        dist_row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        dist_layout = QHBoxLayout(dist_row)
        dist_layout.setContentsMargins(0, 0, 0, 0)
        dist_layout.setSpacing(8)

        set_btn = _sidebar_btn(QPushButton("Align image…"))
        set_btn.setObjectName("ls-dist-set")
        set_btn.setIcon(lucide.icon("move-3d", 14, theme.PURPLE))
        set_btn.setStyleSheet(_DIST_SET_BTN)
        set_btn.setToolTip(
            "Place 3 matching points to align the reference image with the stage."
        )
        set_btn.clicked.connect(self._open_distortion_overlay)
        self._ref_set_dist_btn = set_btn
        dist_layout.addWidget(set_btn, stretch=1)

        reset_btn = _sidebar_btn(QPushButton("Reset alignment"))
        reset_btn.setStyleSheet(theme.GHOST_BTN)
        reset_btn.setToolTip("Remove the reference image alignment transform.")
        reset_btn.clicked.connect(self._reset_reference_distortion)
        self._ref_reset_btn = reset_btn
        dist_layout.addWidget(reset_btn)
        layout.addWidget(dist_row)

        align_hint = QLabel(
            "Maps the reference image onto the stage using 3 matching points "
            "(affine transform). Does not correct the live camera feed."
        )
        align_hint.setWordWrap(True)
        align_hint.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        align_hint.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; background: transparent;"
        )
        layout.addWidget(align_hint)

        camera = self._window.instruments.camera
        if camera is not None:
            layout.addWidget(theme.separator())
            layout.addWidget(
                theme.section_title("Camera distortion correction", "grid-3x3")
            )

            cam_status_row = QWidget()
            cam_status_row.setFixedHeight(theme.BTN_MIN_H)
            cam_status_row.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
            )
            cam_status_row.setStyleSheet(
                f"background: {theme.BG_CARD}; border: 1px solid {theme.BORDER};"
                " border-radius: 5px;"
            )
            cam_status_layout = QHBoxLayout(cam_status_row)
            cam_status_layout.setContentsMargins(10, 0, 10, 0)
            cam_key = QLabel("CORRECTION")
            cam_key.setStyleSheet(_MONO_MUTED)
            cam_status_layout.addWidget(cam_key)
            cam_status_layout.addStretch()
            self._ref_cam_status_val = QLabel("NONE")
            self._ref_cam_status_val.setStyleSheet(
                f"color: {theme.TEXT_DIM}; font-family: monospace;"
                " font-size: 11px; background: transparent;"
            )
            cam_status_layout.addWidget(self._ref_cam_status_val)
            layout.addWidget(cam_status_row)

            wizard_btn = _sidebar_btn(QPushButton("Launch distortion wizard"))
            wizard_btn.setIcon(lucide.icon("grid-3x3", 14, theme.TEXT_DIM))
            wizard_btn.setStyleSheet(theme.GHOST_BTN)
            wizard_btn.setEnabled(False)
            wizard_btn.setToolTip(
                "Corrects optical distortion on the live camera feed when the "
                "sensor is tilted off-axis. Available in the classic UI "
                "(Camera dock → Distortion Wizard)."
            )
            layout.addWidget(wizard_btn)

            cam_hint = QLabel(
                "Separate from reference alignment: this corrects the camera "
                "image itself (quad-to-quad), not the overlay image."
            )
            cam_hint.setWordWrap(True)
            cam_hint.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
            )
            cam_hint.setStyleSheet(
                f"color: {theme.TEXT_DIM}; font-size: 10px; background: transparent;"
            )
            layout.addWidget(cam_hint)

        _compact_panel(layout)
        self._sync_reference_panel()
        return panel

    def _build_lasers_panel(self) -> QWidget:
        panel = QWidget()
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(PANEL_SPACING)
        lasers = self._window.instruments.lasers
        for i, laser in enumerate(lasers):
            layout.addWidget(_LaserSection(laser, i))
            if i < len(lasers) - 1:
                layout.addWidget(theme.separator())
        _compact_panel(layout)
        return panel

    @staticmethod
    def _placeholder(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl

    def _on_position_changed(self, position: Vector) -> None:
        if self._coord_label is not None:
            self._coord_label.setText(_format_coords(list(position.data)))

    def _on_click_move_toggled(self, checked: bool) -> None:
        viewer = self._window.viewer
        if viewer is None:
            return
        if checked:
            viewer.select_mode(Viewer.Mode.STAGE)
        else:
            viewer.select_mode(Viewer.Mode.NONE)

    def _on_viewer_mode_changed(self, mode_id: int) -> None:
        btn = self._click_move_btn
        if btn is None:
            return
        active = mode_id == int(Viewer.Mode.STAGE)
        btn.blockSignals(True)
        btn.setChecked(active)
        btn.setIcon(lucide.icon("move", 15, theme.PURPLE if active else theme.TEXT))
        btn.blockSignals(False)

    def _save_memory_point(self) -> None:
        viewer = self._window.viewer
        if viewer is not None:
            viewer.add_marker()

    def _browse_reference(self) -> None:
        viewer = self._window.viewer
        if viewer is not None:
            viewer.load_picture()
            if viewer.has_background_picture and viewer.background_opacity == 100:
                viewer.set_background_opacity(55)
            self._sync_reference_panel()

    def _clear_reference(self) -> None:
        viewer = self._window.viewer
        if viewer is not None:
            viewer.clear_picture()
            self._sync_reference_panel()

    def _on_ref_opacity_changed(self, value: int) -> None:
        viewer = self._window.viewer
        if viewer is not None:
            viewer.set_background_opacity(value)

    def _open_distortion_overlay(self) -> None:
        area = self._window._viewer_area
        overlay = area.show_distortion_overlay()
        if not self._distortion_wired:
            overlay.applied.connect(self._sync_reference_panel)
            overlay.cancelled.connect(self._sync_reference_panel)
            self._distortion_wired = True

    def _reset_reference_distortion(self) -> None:
        viewer = self._window.viewer
        if viewer is not None:
            viewer.reset_background_alignment()
            self._sync_reference_panel()

    def _sync_reference_panel(self) -> None:
        viewer = self._window.viewer
        has_image = viewer is not None and viewer.has_background_picture
        aligned = viewer is not None and viewer.background_is_aligned

        if self._ref_trash_btn is not None:
            self._ref_trash_btn.setEnabled(has_image)
        if self._ref_set_dist_btn is not None:
            self._ref_set_dist_btn.setEnabled(has_image)
        if self._ref_reset_btn is not None:
            self._ref_reset_btn.setEnabled(has_image and aligned)

        if self._ref_opacity is not None:
            self._ref_opacity.setEnabled(has_image)
            if viewer is not None:
                self._ref_opacity.set_value(viewer.background_opacity)

        if self._ref_status_val is not None:
            if aligned:
                self._ref_status_val.setText("ALIGNED · AFFINE")
                self._ref_status_val.setStyleSheet(
                    f"color: {theme.GREEN}; font-family: monospace; font-size: 11px;"
                    " background: transparent;"
                )
            else:
                self._ref_status_val.setText("NONE")
                self._ref_status_val.setStyleSheet(
                    f"color: {theme.TEXT_DIM}; font-family: monospace; font-size: 11px;"
                    " background: transparent;"
                )

        if self._ref_cam_status_val is not None:
            camera = self._window.instruments.camera
            cam_corrected = camera is not None and camera.correction_matrix is not None
            if cam_corrected:
                self._ref_cam_status_val.setText("CORRECTED · QUAD-TO-QUAD")
                self._ref_cam_status_val.setStyleSheet(
                    f"color: {theme.GREEN}; font-family: monospace;"
                    " font-size: 11px; background: transparent;"
                )
            else:
                self._ref_cam_status_val.setText("NONE")
                self._ref_cam_status_val.setStyleSheet(
                    f"color: {theme.TEXT_DIM}; font-family: monospace;"
                    " font-size: 11px; background: transparent;"
                )
