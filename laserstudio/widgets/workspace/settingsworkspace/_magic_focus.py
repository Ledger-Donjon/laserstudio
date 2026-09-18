"""Magic focus: coarse/fine search settings, launch/interrupt, and a live
sharpness readout — port of the classic FocusToolBar's magic-focus half."""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from laserstudio.instruments.camera import CameraInstrument
from laserstudio.instruments.focus import FocusInstrument, FocusSearchSettings
from laserstudio.widgets.newui import lucide, theme
from laserstudio.widgets.toolbars.focustoolbar import FocusChart
from laserstudio.widgets.workspace.schemaform import _INPUT_SS, ToggleSwitch

from ._helpers import _mono_label
from ._styles import _FIELD_CONTROL_H, PANEL_SPACING


class _FocusSearchSettingsGroup(QWidget):
    """Editable span/steps/averaging/multi-peaks/best-is-highest-z fields for
    one :class:`FocusSearchSettings` instance."""

    def __init__(
        self, title: str, settings: FocusSearchSettings, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._settings = settings

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        header = QLabel(title)
        header.setStyleSheet(
            f"color: {theme.TEXT}; font-family: 'Brut Grotesque'; font-weight: 700;"
            " font-size: 12px; background: transparent;"
        )
        root.addWidget(header)

        self._span = self._double_field(1.0, 10000.0, "\xa0µm")
        self._span.setValue(settings.span)
        self._span.valueChanged.connect(self._on_changed)
        root.addWidget(self._field_row("Span", self._span))

        self._steps = self._int_field(2, 100)
        self._steps.setValue(settings.steps)
        self._steps.valueChanged.connect(self._on_changed)
        root.addWidget(self._field_row("Steps", self._steps))

        self._averaging = self._int_field(1, 100)
        self._averaging.setValue(settings.averaging)
        self._averaging.valueChanged.connect(self._on_changed)
        root.addWidget(self._field_row("Averaging", self._averaging))

        self._multi_peaks = QCheckBox("Multi peaks")
        self._multi_peaks.setChecked(settings.multi_peaks)
        self._multi_peaks.toggled.connect(self._on_changed)
        root.addWidget(self._multi_peaks)

        self._best_is_highest_z = QCheckBox("Best is highest Z")
        self._best_is_highest_z.setChecked(settings.best_is_highest_z)
        self._best_is_highest_z.toggled.connect(self._on_changed)
        root.addWidget(self._best_is_highest_z)

    def _field_row(self, label: str, control: QWidget) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        lbl = _mono_label(label)
        lbl.setFixedWidth(70)
        layout.addWidget(lbl)
        control.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(control)
        return row

    def _double_field(self, minimum: float, maximum: float, suffix: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setStyleSheet(_INPUT_SS)
        spin.setFixedHeight(_FIELD_CONTROL_H)
        spin.setMinimum(minimum)
        spin.setMaximum(maximum)
        spin.setDecimals(1)
        spin.setSuffix(suffix)
        return spin

    def _int_field(self, minimum: int, maximum: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setStyleSheet(_INPUT_SS)
        spin.setFixedHeight(_FIELD_CONTROL_H)
        spin.setMinimum(minimum)
        spin.setMaximum(maximum)
        return spin

    def _on_changed(self, *_args: object) -> None:
        self._settings.span = self._span.value()
        self._settings.steps = self._steps.value()
        self._settings.averaging = self._averaging.value()
        self._settings.multi_peaks = self._multi_peaks.isChecked()
        self._settings.best_is_highest_z = self._best_is_highest_z.isChecked()


class _MagicFocusSection(QWidget):
    """Coarse/fine magic-focus settings, launch/interrupt button, live
    sharpness readout, and a popped-out chart of the search results."""

    def __init__(self, window: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self._focus_helper: FocusInstrument = window.instruments.focus_helper
        self._camera: CameraInstrument = window.instruments.camera

        if self._focus_helper.coarse_focus_settings is None:
            self._focus_helper.coarse_focus_settings = FocusSearchSettings()

        self._chart = FocusChart()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(PANEL_SPACING)

        root.addWidget(theme.section_title("Magic focus", "scan-eye"))
        root.addWidget(
            self._hint(
                "Automatically finds the best focus by sweeping Z and analysing "
                "image sharpness."
            )
        )

        root.addWidget(
            _FocusSearchSettingsGroup("Coarse", self._focus_helper.coarse_focus_settings)
        )

        self._fine_toggle = ToggleSwitch(self._focus_helper.fine_focus_settings is not None)
        self._fine_toggle.toggled.connect(self._on_fine_toggled)
        fine_header = QHBoxLayout()
        fine_lbl = QLabel("Fine pass")
        fine_lbl.setStyleSheet(
            f"color: {theme.TEXT}; font-family: 'Brut Grotesque'; font-weight: 700;"
            " font-size: 12px; background: transparent;"
        )
        fine_header.addWidget(fine_lbl)
        fine_header.addStretch()
        fine_header.addWidget(self._fine_toggle)
        root.addLayout(fine_header)

        self._fine_group_holder = QVBoxLayout()
        root.addLayout(self._fine_group_holder)
        self._fine_group: _FocusSearchSettingsGroup | None = None
        self._rebuild_fine_group()

        root.addWidget(theme.separator())

        run_row = QHBoxLayout()
        run_row.setSpacing(8)
        self._run_btn = QPushButton("Run magic focus")
        self._run_btn.setStyleSheet(theme.GHOST_BTN)
        self._run_btn.setIcon(lucide.icon("scan", 14, theme.TEXT))
        self._run_btn.clicked.connect(self._on_run_clicked)
        run_row.addWidget(self._run_btn, 1)

        self._sharpness_lbl = QLabel("—")
        self._sharpness_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sharpness_lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-family: monospace; font-size: 10px;"
            " background: transparent;"
        )
        self._sharpness_lbl.setToolTip("Sharpness (Laplacian std dev) of the current image.")
        run_row.addWidget(self._sharpness_lbl)
        root.addLayout(run_row)

        self._camera.new_image.connect(self._on_new_image)

    # ── construction helpers ──────────────────────────────────────────────────
    def _hint(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; background: transparent;"
        )
        return lbl

    def _rebuild_fine_group(self) -> None:
        if self._fine_group is not None:
            self._fine_group_holder.removeWidget(self._fine_group)
            self._fine_group.deleteLater()
            self._fine_group = None
        settings = self._focus_helper.fine_focus_settings
        if settings is not None:
            group = _FocusSearchSettingsGroup("Fine", settings)
            self._fine_group_holder.addWidget(group)
            self._fine_group = group

    # ── UI → model ──────────────────────────────────────────────────────────
    def _on_fine_toggled(self, enabled: bool) -> None:
        if enabled and self._focus_helper.fine_focus_settings is None:
            self._focus_helper.fine_focus_settings = FocusSearchSettings()
        elif not enabled:
            self._focus_helper.fine_focus_settings = None
        self._rebuild_fine_group()

    def _on_run_clicked(self) -> None:
        thread = self._focus_helper.focus_thread
        if thread is not None and thread.isRunning():
            thread.requestInterruption()
            thread.wait()
            self._run_btn.setText("Run magic focus")
            return

        self._chart.clear()
        self._chart.show()
        try:
            t = self._focus_helper.magic_focus()
        except Exception as exc:
            logging.getLogger("laserstudio").warning(f"Magic focus failed to start: {exc}")
            return
        t.new_point.connect(
            lambda z, dev: self._chart.new_point(
                z, dev, self._chart.coarse_serie if t.tab_coarse is None else self._chart.fine_serie
            )
        )
        t.finished.connect(self._on_finished)
        self._chart.setRange(t.z_range())
        self._run_btn.setText("Interrupt magic focus")
        t.start()

    def _on_finished(self) -> None:
        self._run_btn.setText("Run magic focus")
        thread = self._focus_helper.focus_thread
        if thread is not None:
            self._chart.vmarker = thread.best_z
        self._chart.show()

    def _on_new_image(self) -> None:
        self._sharpness_lbl.setText(f"{self._camera.laplacian_std_dev:.2f}")
