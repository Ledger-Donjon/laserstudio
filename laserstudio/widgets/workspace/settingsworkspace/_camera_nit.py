"""Gain (manual + AGC), averaging, and shading correction for NIT cameras."""

from __future__ import annotations

import logging
import pickle
from typing import Any

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from laserstudio.widgets.newui import theme
from laserstudio.widgets.return_line_edit import ReturnDoubleSpinBox, ReturnSpinBox
from laserstudio.widgets.workspace.schemaform import _INPUT_SS

from ._helpers import _param_grid_cell, _two_col_param_grid
from ._styles import _CLICK_MOVE_BTN, _FIELD_CONTROL_H, PANEL_SPACING

_AGC_INTERVAL_MS = 1000


class _CameraNITSection(QWidget):
    """Gain (manual bounds + AGC loop), averaging, and shading correction.

    Port of the classic ``CameraNITDockWidget``, minus the objective selector
    (already handled by the shared objective combo box in
    ``_build_camera_panel``).

    ``camera`` is typed ``Any`` on purpose. The real ``CameraNITInstrument``
    requires the private ``pynit`` driver (unavailable in most environments,
    including this one and its tests), so this section only relies on the
    small NIT-specific duck type it actually uses (``gain``, ``gain_autoset``,
    ``averaging``, ``shade_correction``, ``shade_correct``,
    ``clear_shade_correction``, ``objective``, ``parameter_changed``) instead
    of importing the concrete class. Deciding whether a given camera actually
    is a NIT camera is the caller's responsibility.
    """

    def __init__(self, camera: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._camera = camera
        self._updating = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(PANEL_SPACING)

        root.addWidget(theme.section_title("NIT camera", "camera"))

        # Manual gain bounds (low/high), applied on Enter.
        self._gain_low = self._double_field(0.0, float(0xFFFF))
        self._gain_low.returnPressed2.connect(self._on_gain_changed)
        self._gain_high = self._double_field(0.0, float(0xFFFF))
        self._gain_high.returnPressed2.connect(self._on_gain_changed)
        root.addWidget(
            _two_col_param_grid(
                [
                    ("GAIN LOW", self._gain_low),
                    ("GAIN HIGH", self._gain_high),
                ]
            )
        )

        # AGC: while checked, periodically calls gain_autoset() and reflects
        # the returned bounds on the two fields above.
        self._agc_btn = QPushButton("AGC")
        self._agc_btn.setObjectName("ls-click-move-btn")
        self._agc_btn.setStyleSheet(_CLICK_MOVE_BTN)
        self._agc_btn.setToolTip(
            f"Auto gain control (every {_AGC_INTERVAL_MS / 1000:g} second)"
        )
        self._agc_btn.setCheckable(True)
        self._agc_btn.toggled.connect(self._on_agc_toggled)
        root.addWidget(self._agc_btn)

        self._agc_timer = QTimer(self)
        self._agc_timer.setInterval(_AGC_INTERVAL_MS)
        self._agc_timer.timeout.connect(self._on_gain_autoset)

        # Averaging, applied on Enter.
        self._averaging_spin = ReturnSpinBox()
        self._averaging_spin.setStyleSheet(_INPUT_SS)
        self._averaging_spin.setFixedHeight(_FIELD_CONTROL_H)
        self._averaging_spin.setMinimum(1)
        self._averaging_spin.setMaximum(255)
        self._averaging_spin.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._averaging_spin.returnPressed2.connect(self._on_averaging_changed)
        root.addWidget(_param_grid_cell("AVERAGING", self._averaging_spin))

        # Shading correction: use/clear the current image, or save/load one
        # from disk (pickled numpy array, same format as the classic dock).
        shade_row = QWidget()
        shade_row.setStyleSheet("background: transparent;")
        shade_layout = QHBoxLayout(shade_row)
        shade_layout.setContentsMargins(0, 0, 0, 0)
        shade_layout.setSpacing(8)

        shade_btn = QPushButton("Shade")
        shade_btn.setToolTip("Set current image as shading correction")
        shade_btn.setStyleSheet(theme.GHOST_BTN)
        shade_btn.clicked.connect(self._on_shade_correct)
        shade_layout.addWidget(shade_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setToolTip("Clear shading correction")
        clear_btn.setStyleSheet(theme.GHOST_BTN)
        clear_btn.clicked.connect(self._on_clear_shade_correction)
        shade_layout.addWidget(clear_btn)

        save_btn = QPushButton("Save")
        save_btn.setToolTip("Save shading correction")
        save_btn.setStyleSheet(theme.GHOST_BTN)
        save_btn.clicked.connect(self._on_shade_save)
        shade_layout.addWidget(save_btn)

        load_btn = QPushButton("Load")
        load_btn.setToolTip("Load shading correction")
        load_btn.setStyleSheet(theme.GHOST_BTN)
        load_btn.clicked.connect(self._on_shade_load)
        shade_layout.addWidget(load_btn)

        root.addWidget(shade_row)

        self._refresh_gain()
        self._refresh_averaging()

        camera.parameter_changed.connect(self._on_param)

    # ── construction helpers ──────────────────────────────────────────────────

    def _double_field(self, minimum: float, maximum: float) -> ReturnDoubleSpinBox:
        spin = ReturnDoubleSpinBox()
        spin.setStyleSheet(_INPUT_SS)
        spin.setFixedHeight(_FIELD_CONTROL_H)
        spin.setMinimum(minimum)
        spin.setMaximum(maximum)
        spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return spin

    # ── device interaction ────────────────────────────────────────────────────

    def _refresh_gain(self) -> None:
        try:
            low, high = self._camera.gain
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to read the NIT camera gain: {exc}"
            )
            return
        self._set_gain(float(low), float(high))

    def _refresh_averaging(self) -> None:
        try:
            averaging = self._camera.averaging
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to read the NIT camera averaging: {exc}"
            )
            return
        self._set_averaging(int(averaging))

    def _set_gain(self, low: float, high: float) -> None:
        self._updating = True
        try:
            self._gain_low.blockSignals(True)
            self._gain_high.blockSignals(True)
            self._gain_low.setValue(low)
            self._gain_high.setValue(high)
            self._gain_low.reset()
            self._gain_high.reset()
        finally:
            self._gain_low.blockSignals(False)
            self._gain_high.blockSignals(False)
            self._updating = False

    def _set_averaging(self, value: int) -> None:
        self._updating = True
        try:
            self._averaging_spin.blockSignals(True)
            self._averaging_spin.setValue(value)
            self._averaging_spin.reset()
        finally:
            self._averaging_spin.blockSignals(False)
            self._updating = False

    def _on_gain_changed(self) -> None:
        if self._updating:
            return
        low = self._gain_low.value()
        high = self._gain_high.value()
        if low > high:
            low, high = high, low
            self._set_gain(low, high)
        try:
            self._camera.gain = (float(low), float(high))
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to set the NIT camera gain: {exc}"
            )

    def _on_gain_autoset(self) -> None:
        try:
            low, high = self._camera.gain_autoset()
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to auto-set the NIT camera gain: {exc}"
            )
            return
        self._set_gain(float(low), float(high))

    def _on_agc_toggled(self, checked: bool) -> None:
        if checked:
            # Apply gain correction immediately, don't wait for the timer.
            self._on_gain_autoset()
            self._agc_timer.start()
        else:
            self._agc_timer.stop()

    def _on_averaging_changed(self) -> None:
        if self._updating:
            return
        try:
            self._camera.averaging = self._averaging_spin.value()
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to set the NIT camera averaging: {exc}"
            )

    def _on_shade_correct(self) -> None:
        try:
            self._camera.shade_correct()
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to set the shading correction: {exc}"
            )

    def _on_clear_shade_correction(self) -> None:
        try:
            self._camera.clear_shade_correction()
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to clear the shading correction: {exc}"
            )

    def _default_shade_filename(self) -> str:
        try:
            objective = float(self._camera.objective)
        except Exception:
            objective = 0.0
        return f"shade-{objective:.0f}x.pickle"

    def _on_shade_save(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Save shading correction",
            self._default_shade_filename(),
            "Pickle files (*.pickle);;All files (*)",
        )
        if not path:
            return
        try:
            data = self._camera.shade_correction
            with open(path, "wb") as f:
                pickle.dump(data, f)
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to save the shading correction to {path}: {exc}"
            )
            QMessageBox.critical(
                self, "Error", f"Failed to save shading correction: {exc}"
            )

    def _on_shade_load(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Load shading correction",
            self._default_shade_filename(),
            "Pickle files (*.pickle);;All files (*)",
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                self._camera.shade_correction = pickle.load(f)
        except FileNotFoundError:
            QMessageBox.critical(self, "Error", "Shading correction file not found.")
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to load the shading correction from {path}: {exc}"
            )
            QMessageBox.critical(
                self, "Error", f"Failed to load shading correction: {exc}"
            )

    def _on_param(self, parameter: str, value: Any) -> None:
        if (
            parameter == "gain"
            and isinstance(value, (list, tuple))
            and len(value) == 2
        ):
            try:
                self._set_gain(float(value[0]), float(value[1]))
            except (TypeError, ValueError):
                pass
        elif parameter == "averaging" and isinstance(value, (int, float)):
            self._set_averaging(int(value))
