"""Light heading with its on/off switch + the intensity slider."""

from __future__ import annotations

import logging

from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from laserstudio.instruments.light import LightInstrument
from laserstudio.widgets.newui import lucide, theme
from laserstudio.widgets.workspace.schemaform import ToggleSwitch

from ._helpers import _SliderRow
from ._styles import _MONO_DIM, PANEL_SPACING


class _LightSection(QWidget):
    """Light heading with its on/off switch + the intensity slider."""

    def __init__(self, light: LightInstrument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._light = light
        # Guards the toggle against writing back what we just read from the device.
        self._updating = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(PANEL_SPACING)

        header = QWidget()
        header.setStyleSheet("background: transparent;")
        head = QHBoxLayout(header)
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(9)
        icon = QLabel()
        icon.setPixmap(lucide.pixmap("lightbulb", 16, theme.PURPLE))
        icon.setFixedWidth(20)
        icon.setStyleSheet("background: transparent;")
        head.addWidget(icon)
        title = QLabel("Light")
        title.setStyleSheet(
            f"color: {theme.TEXT}; font-family: 'Brut Grotesque'; font-weight: 700;"
            " font-size: 15px; background: transparent;"
        )
        head.addWidget(title)
        head.addStretch()
        driver = QLabel(type(light).__name__.replace("Instrument", "").upper())
        driver.setStyleSheet(_MONO_DIM)
        head.addWidget(driver)
        self._toggle = ToggleSwitch(self._read_state())
        self._toggle.setToolTip("Switch the light source on or off")
        self._toggle.toggled.connect(self._on_toggled)
        head.addWidget(self._toggle)
        root.addWidget(header)

        self._slider = _SliderRow(
            "LIGHT LEVEL",
            0,
            100,
            int(self._read_intensity() * 100),
            lambda v: f"{v} %",
            self._on_intensity,
        )
        root.addWidget(self._slider)

        light.parameter_changed.connect(self._on_param)

    def showEvent(self, a0: QShowEvent | None) -> None:  # noqa: N802 (Qt override)
        super().showEvent(a0)
        # The classic lighting dock drives the same instrument without telling us.
        self._set_toggle(self._read_state())
        self._slider.set_value(int(self._read_intensity() * 100))

    # ── device interaction ────────────────────────────────────────────────────
    def _read_state(self) -> bool:
        try:
            return bool(self._light.light)
        except Exception as exc:  # keep the UI responsive on device errors
            logging.getLogger("laserstudio").warning(
                f"Failed to read the light state: {exc}"
            )
            return False

    def _read_intensity(self) -> float:
        try:
            return float(self._light.intensity)
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to read the light intensity: {exc}"
            )
            return 0.0

    def _on_toggled(self, on: bool) -> None:
        if self._updating:
            return
        try:
            self._light.light = on
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to switch the light: {exc}"
            )
        # Show what the device actually does, not what was asked.
        self._set_toggle(self._read_state())

    def _on_intensity(self, value: int) -> None:
        try:
            self._light.intensity = value / 100.0
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to set the light intensity: {exc}"
            )

    def _on_param(self, parameter: str, value: object) -> None:
        if parameter == "light":
            self._set_toggle(bool(value))
        elif parameter == "intensity" and isinstance(value, (int, float)):
            self._slider.set_value(int(float(value) * 100))

    def _set_toggle(self, on: bool) -> None:
        self._updating = True
        try:
            self._toggle.setChecked(on)
        finally:
            self._updating = False
