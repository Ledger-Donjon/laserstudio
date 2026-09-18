"""Controls for one laser: ARM, pulse power, offset current, pulse width/delay."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from laserstudio.widgets.newui import lucide, theme
from laserstudio.widgets.return_line_edit import ReturnDoubleSpinBox, ReturnSpinBox
from laserstudio.widgets.viewer import Viewer
from laserstudio.widgets.workspace.schemaform import _INPUT_SS

from ._helpers import _param_grid_cell, _readout_field, _two_col_param_grid
from ._optispot import _OptispotSection
from ._probe import _ProbeOffsetControl
from ._styles import (
    _FIELD_CONTROL_H,
    _LASER_ARM_ARMED_SS,
    _LASER_ARM_SAFE_SS,
    _MONO_DIM,
    _MONO_MUTED,
    PANEL_SPACING,
)

# PDM lasers are optional (require the pypdm driver); import defensively so the
# whole Settings UI still loads if the driver is unavailable.
try:
    from laserstudio.instruments.pdm import InterlockStatus, PDMInstrument
except ImportError:  # pragma: no cover - pypdm is an optional dependency
    PDMInstrument = None  # type: ignore[assignment,misc]
    InterlockStatus = None  # type: ignore[assignment,misc]


class _LaserSection(QWidget):
    """Controls for one laser: ARM (on/off), pulse power, offset current,
    pulse width and delay, plus read-only interlock status and temperature.

    Behaviour mirrors the classic PDM dock (``PDMDockWidget``): editable numeric
    values are applied on Enter (not on every keystroke) to avoid flooding the
    device, and the widgets track the instrument via ``parameter_changed``.
    Sweep controls are intentionally omitted for now.
    """

    def __init__(
        self,
        laser: Any,
        index: int,
        viewer: Viewer | None,
        parent: QWidget | None = None,
    ) -> None:
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
        root.addWidget(_ProbeOffsetControl(laser, viewer))

        optispot = getattr(laser, "optispot", None)
        if optispot is not None:
            root.addWidget(_OptispotSection(optispot))

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
