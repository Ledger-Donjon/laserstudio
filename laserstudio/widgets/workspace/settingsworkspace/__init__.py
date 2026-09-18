"""Settings workspace — sub-category panels (camera, positioning, focus, …)."""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from laserstudio.instruments.camera_usb import CameraUSBInstrument
from laserstudio.instruments.stage import Vector
from laserstudio.instruments.stage_pi import PIStageInstrument
from laserstudio.widgets.newui import lucide, theme
from laserstudio.widgets.viewer import Viewer
from laserstudio.widgets.workspace.schemaform import _INPUT_SS
from laserstudio.widgets.workspace.workspace import Workspace

from ._dpad import DpadWidget, SubCategoryBar, _SubPanelStack
from ._helpers import (
    _compact_panel,
    _format_coords,
    _sidebar_btn,
    _SliderRow,
    _two_col_param_grid,
    pixel_size_um,
    _readout_field,
)
from ._joystick import _JoystickControls
from ._laser import _LaserSection
from ._light import _LightSection
from ._optispot import _OptispotSection
from ._pi_motion import _PIMotionSection
from ._probe import _ProbeOffsetControl, _ProbeSection
from ._safety_limits import _SafetyLimitsSection
from ._shutter import _ShutterSection
from ._styles import (
    _CLICK_MOVE_BTN,
    _DIST_SET_BTN,
    _FIELD_CONTROL_H,
    _MONO_MUTED,
    _TRASH_BTN_SS,
    PANEL_SPACING,
)

__all__ = [
    "SettingsWorkspace",
    "_two_col_param_grid",
    "_JoystickControls",
    "_LaserSection",
    "_OptispotSection",
    "_ProbeOffsetControl",
    "_ProbeSection",
]


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
        super().__init__()
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
        if self._window.instruments.probes:
            tabs.append(("probes", "Probes", "crosshair"))
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
        if self._window.instruments.probes:
            self._sub_stack.addWidget(self._build_probes_panel())
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

    def on_activated(self) -> None:
        viewer = self._window.viewer
        if viewer is not None and self._click_move_btn is not None:
            self._on_viewer_mode_changed(int(viewer.mode))

    def on_deactivated(self) -> None:
        """Leave click-and-move mode when switching to another workspace tab."""
        viewer = self._window.viewer
        if viewer is not None and viewer.mode in (
            Viewer.Mode.STAGE,
            Viewer.Mode.PROBE_OFFSET,
        ):
            viewer.select_mode(Viewer.Mode.NONE)

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
        for mag in camera.objectives:
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
                logging.getLogger("laserstudio").error("Failed to add exposure slider")
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
                logging.getLogger("laserstudio").error("Failed to add gain slider")
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
                logging.getLogger("laserstudio").error(
                    "Failed to add brightness slider"
                )
                pass

        # Light
        light = self._window.instruments.light
        if light is not None:
            layout.addWidget(theme.separator())
            layout.addWidget(_LightSection(light))

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
                "Shortcut: M — click again or Esc to deselect."
            )
            btn.clicked.connect(self._on_click_move_clicked)
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
            if stage.supports_analog_joystick:
                layout.addWidget(_JoystickControls(stage))
            stage.position_changed.connect(self._on_position_changed)
            self._on_position_changed(stage.position)

            layout.addWidget(theme.separator())
            layout.addWidget(_SafetyLimitsSection(self._window))
            if isinstance(stage, PIStageInstrument):
                layout.addWidget(theme.separator())
                layout.addWidget(_PIMotionSection(stage))
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
        status_row.setObjectName("ls-ref-status-row")
        status_row.setFixedHeight(theme.BTN_MIN_H)
        status_row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        status_row.setStyleSheet(
            f"QWidget#ls-ref-status-row {{ background: {theme.BG_CARD};"
            f" border: 1px solid {theme.BORDER}; border-radius: 5px; }}"
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
            cam_status_row.setObjectName("ls-cam-status-row")
            cam_status_row.setFixedHeight(theme.BTN_MIN_H)
            cam_status_row.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
            )
            # Scope the border to the row itself (see reference status row above).
            cam_status_row.setStyleSheet(
                f"QWidget#ls-cam-status-row {{ background: {theme.BG_CARD};"
                f" border: 1px solid {theme.BORDER}; border-radius: 5px; }}"
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

    def _build_probes_panel(self) -> QWidget:
        panel = QWidget()
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(PANEL_SPACING)
        probes = self._window.instruments.probes
        for i, probe in enumerate(probes):
            layout.addWidget(_ProbeSection(probe, i, self._window.viewer))
            if i < len(probes) - 1:
                layout.addWidget(theme.separator())
        _compact_panel(layout)
        return panel

    def _build_lasers_panel(self) -> QWidget:
        panel = QWidget()
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(PANEL_SPACING)
        lasers = self._window.instruments.lasers
        for i, laser in enumerate(lasers):
            layout.addWidget(_LaserSection(laser, i, self._window.viewer))
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

    def _on_click_move_clicked(self) -> None:
        viewer = self._window.viewer
        if viewer is None:
            return
        viewer.select_mode(Viewer.Mode.STAGE, toggle=True)

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
