"""Refresh interval, resolution, show/hide image, and the calibration wizards.

Port of the (non-shutter, non-objective) part of the classic
``CameraDockWidget``: those two are already handled elsewhere in the redesigned
Settings workspace (``_ShutterSection`` and the objective/pixel-size grid built
by ``_build_camera_panel``), so this section does not duplicate them.
"""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from laserstudio.instruments.camera import CameraInstrument
from laserstudio.instruments.camera_usb import CameraUSBInstrument
from laserstudio.widgets.camerawizards import CameraDistortionWizard, ProbesPositionWizard
from laserstudio.widgets.newui import lucide, theme
from laserstudio.widgets.return_line_edit import ReturnSpinBox
from laserstudio.widgets.toolbars.cameradockwidget import (
    _resolution_combobox_index,
    _resolution_label,
)
from laserstudio.widgets.viewer import Viewer
from laserstudio.widgets.workspace.schemaform import _INPUT_SS

from ._helpers import _param_grid_cell, _two_col_param_grid
from ._styles import _CLICK_MOVE_BTN, _FIELD_CONTROL_H, PANEL_SPACING


class _CameraGenericSection(QWidget):
    """Refresh interval, resolution, image visibility and calibration wizards.

    ``laser_studio`` is the main application object (exposing ``.instruments``
    and ``.viewer``, like the classic ``LaserStudio`` window): it is required by
    the ``CameraDistortionWizard``/``ProbesPositionWizard`` wizards themselves,
    which need more context than just the camera and the viewer (the list of
    configured probes/lasers in particular). It is optional here so this
    section stays usable/testable with just a camera and a viewer; when it is
    not provided, the wizard buttons are simply disabled/hidden.
    """

    def __init__(
        self,
        camera: CameraInstrument,
        viewer: Viewer | None,
        laser_studio: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._camera = camera
        self._viewer = viewer
        self._laser_studio = laser_studio
        self._distortion_wizard: CameraDistortionWizard | None = None
        self._probes_wizard: ProbesPositionWizard | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(PANEL_SPACING)

        # Show / hide the camera image in the main viewer.
        self._show_hide_btn = QPushButton()
        self._show_hide_btn.setObjectName("ls-click-move-btn")
        self._show_hide_btn.setStyleSheet(_CLICK_MOVE_BTN)
        self._show_hide_btn.setToolTip("Show/Hide the camera image in the viewer")
        self._show_hide_btn.setCheckable(True)
        stage_sight = viewer.stage_sight if viewer is not None else None
        self._show_hide_btn.setEnabled(stage_sight is not None)
        self._sync_show_hide_button(
            bool(stage_sight.show_image) if stage_sight is not None else True
        )
        self._show_hide_btn.toggled.connect(self._on_show_hide_toggled)
        root.addWidget(self._show_hide_btn)

        # Refresh interval, applied on Enter (see ReturnSpinBox).
        self._refresh_spin = ReturnSpinBox()
        self._refresh_spin.setStyleSheet(_INPUT_SS)
        self._refresh_spin.setFixedHeight(_FIELD_CONTROL_H)
        self._refresh_spin.setSuffix("\xa0ms")
        self._refresh_spin.setMinimum(2)
        self._refresh_spin.setMaximum(10000)
        self._refresh_spin.setSingleStep(10)
        self._refresh_spin.setValue(camera.refresh_interval)
        self._refresh_spin.reset()
        self._refresh_spin.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._refresh_spin.returnPressed2.connect(self._on_refresh_interval_changed)

        # Resolution selector, only for USB cameras exposing supported sizes.
        self._resolution_combo: QComboBox | None = None
        if isinstance(camera, CameraUSBInstrument) and camera.supported_resolutions:
            combo = QComboBox()
            combo.setStyleSheet(_INPUT_SS)
            combo.setFixedHeight(_FIELD_CONTROL_H)
            combo.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            combo.blockSignals(True)
            for width, height in camera.supported_resolutions:
                combo.addItem(_resolution_label(width, height), (width, height))
            index = _resolution_combobox_index(combo, camera.width, camera.height)
            if index != -1:
                combo.setCurrentIndex(index)
            combo.blockSignals(False)
            combo.currentIndexChanged.connect(self._on_resolution_changed)
            self._resolution_combo = combo
            root.addWidget(
                _two_col_param_grid(
                    [
                        ("REFRESH INTERVAL", self._refresh_spin),
                        ("RESOLUTION", combo),
                    ]
                )
            )
        else:
            root.addWidget(_param_grid_cell("REFRESH INTERVAL", self._refresh_spin))

        # Calibration wizards (constructed lazily on first use).
        wizard_row = QWidget()
        wizard_row.setStyleSheet("background: transparent;")
        wizard_layout = QHBoxLayout(wizard_row)
        wizard_layout.setContentsMargins(0, 0, 0, 0)
        wizard_layout.setSpacing(8)

        self._distortion_btn = QPushButton("Distortion Wizard")
        self._distortion_btn.setStyleSheet(theme.GHOST_BTN)
        self._distortion_btn.setEnabled(laser_studio is not None)
        self._distortion_btn.setToolTip(
            "Correct optical distortion on the live camera feed."
            if laser_studio is not None
            else "Not available: no application context was provided."
        )
        self._distortion_btn.clicked.connect(self._open_distortion_wizard)
        wizard_layout.addWidget(self._distortion_btn)

        instruments = getattr(laser_studio, "instruments", None)
        has_probes_or_lasers = laser_studio is not None and (
            len(getattr(instruments, "probes", ()))
            + len(getattr(instruments, "lasers", ()))
            > 0
        )
        self._probes_btn = QPushButton("Probes/Spots Wizard")
        self._probes_btn.setStyleSheet(theme.GHOST_BTN)
        self._probes_btn.setHidden(not has_probes_or_lasers)
        self._probes_btn.clicked.connect(self._open_probes_wizard)
        wizard_layout.addWidget(self._probes_btn)

        root.addWidget(wizard_row)

        camera.parameter_changed.connect(self._on_param)

    # ── device interaction ────────────────────────────────────────────────────

    def _sync_show_hide_button(self, shown: bool) -> None:
        self._show_hide_btn.blockSignals(True)
        self._show_hide_btn.setChecked(shown)
        self._show_hide_btn.blockSignals(False)
        self._show_hide_btn.setText("Hide image" if shown else "Show image")
        self._show_hide_btn.setIcon(
            lucide.icon("image", 15, theme.PURPLE if shown else theme.TEXT)
        )

    def _on_show_hide_toggled(self, checked: bool) -> None:
        self._sync_show_hide_button(checked)
        viewer = self._viewer
        if viewer is None or viewer.stage_sight is None:
            return
        try:
            viewer.stage_sight.show_image = checked
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to toggle the camera image visibility: {exc}"
            )

    def _on_refresh_interval_changed(self) -> None:
        try:
            self._camera.refresh_interval = self._refresh_spin.value()
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to set the camera refresh interval: {exc}"
            )

    def _on_resolution_changed(self) -> None:
        combo = self._resolution_combo
        if combo is None:
            return
        resolution = combo.currentData()
        if not isinstance(resolution, tuple) or len(resolution) != 2:
            return
        width, height = resolution
        try:
            self._camera.set_resolution(int(width), int(height))
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                f"Failed to set the camera resolution: {exc}"
            )

    def _open_distortion_wizard(self) -> None:
        laser_studio = self._laser_studio
        if laser_studio is None:
            return
        if self._distortion_wizard is None:
            self._distortion_wizard = CameraDistortionWizard(laser_studio, self)
        self._distortion_wizard.show()

    def _open_probes_wizard(self) -> None:
        laser_studio = self._laser_studio
        if laser_studio is None:
            return
        if self._probes_wizard is None:
            self._probes_wizard = ProbesPositionWizard(laser_studio, self)
        self._probes_wizard.show()

    def _on_param(self, parameter: str, value: Any) -> None:
        if parameter != "resolution" or self._resolution_combo is None:
            return
        if not (
            isinstance(value, (list, tuple))
            and len(value) == 2
            and isinstance(value[0], int)
            and isinstance(value[1], int)
        ):
            return
        combo = self._resolution_combo
        combo.blockSignals(True)
        index = _resolution_combobox_index(combo, value[0], value[1])
        if index != -1:
            combo.setCurrentIndex(index)
        combo.blockSignals(False)
