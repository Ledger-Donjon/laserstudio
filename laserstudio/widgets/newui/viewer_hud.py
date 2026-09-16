"""HUD overlay drawn on top of the spatial viewer."""

from __future__ import annotations

import math
import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QEvent, QObject, QPoint, QSettings, QSize, Qt, QTimer
from PyQt6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
    QShowEvent,
)
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QWidget

from laserstudio.instruments.instruments import Instruments
from laserstudio.instruments.stage_pi import PIStageInstrument

from . import lucide, theme

if TYPE_CHECKING:
    from ..viewer import Viewer

# Shared HUD decoration tokens — used by the viewer overlay and workspace backdrops.
GRID_STEP = 34
GRID_LINE = QColor(255, 255, 255, 7)
BRACKET = QColor(255, 255, 255, 115)  # rgba(255,255,255,0.45)
INSET = 14
BRACKET_LEN = 16
LABEL_INSET = INSET + 4
LABEL_FONT_SIZE = 10
HUD_LABEL_SS = f"color: {theme.TEXT_MUTED}; background: transparent;"

HUD_BTN_SIZE = 28
HUD_BTN_ICON_SIZE = 16
HUD_BTN_SS = f"""
QPushButton {{
    background: rgba(10,10,10,0.55);
    border: 1px solid {theme.BORDER};
    border-radius: 6px;
    color: {theme.TEXT_MUTED};
}}
QPushButton:hover {{
    background: rgba(255,255,255,0.10);
    border: 1px solid {theme.BORDER_HOVER};
    color: {theme.TEXT};
}}
QPushButton:checked {{
    background: {theme.PURPLE_BG};
    border: 1px solid {theme.PURPLE_BORDER};
    color: {theme.PURPLE};
}}
QPushButton:disabled {{
    background: rgba(255,255,255,0.02);
    border: 1px solid {theme.BORDER_SUBTLE};
    color: {theme.TEXT_DIM};
}}
"""

_SCALE_COLOR = QColor(theme.TEXT_MUTED)
_TARGET_BAR_PX = 46.0


def paint_grid_background(
    painter: QPainter, width: int, height: int, *, bg: str = theme.BG_MAIN
) -> None:
    """Fill the widget and draw the 34 px viewer grid."""
    painter.fillRect(0, 0, width, height, QColor(bg))
    painter.setPen(GRID_LINE)
    x = 0
    while x <= width:
        painter.drawLine(x, 0, x, height)
        x += GRID_STEP
    y = 0
    while y <= height:
        painter.drawLine(0, y, width, y)
        y += GRID_STEP


def paint_corner_brackets(painter: QPainter, width: int, height: int) -> None:
    """Draw the four L-shaped corner brackets."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(BRACKET)
    pen.setWidth(1)
    painter.setPen(pen)

    inset = INSET
    blen = BRACKET_LEN
    painter.drawLine(inset, inset, inset + blen, inset)
    painter.drawLine(inset, inset, inset, inset + blen)
    painter.drawLine(width - inset, inset, width - inset - blen, inset)
    painter.drawLine(width - inset, inset, width - inset, inset + blen)
    painter.drawLine(inset, height - inset, inset + blen, height - inset)
    painter.drawLine(inset, height - inset, inset, height - inset - blen)
    painter.drawLine(width - inset, height - inset, width - inset - blen, height - inset)
    painter.drawLine(width - inset, height - inset, width - inset, height - inset - blen)


def make_hud_label(parent: QWidget, text: str = "") -> QLabel:
    """Return a top-left HUD annotation label with consistent font and color."""
    lbl = QLabel(text, parent)
    lbl.setStyleSheet(HUD_LABEL_SS)
    lbl.setFont(theme.mono_font(LABEL_FONT_SIZE))
    return lbl


def _nice_scale(um: float) -> float:
    """Pick a round scale-bar length in µm, on the 1-2-5 sequence.

    Any decade is allowed, so the bar keeps following the zoom below the
    micrometer as well as above the millimeter.
    """
    if not math.isfinite(um) or um <= 0:
        return 1.0
    decade = 10.0 ** math.floor(math.log10(um))
    for multiple in (1.0, 2.0, 5.0):
        value = multiple * decade
        if value >= um:
            return value
    return 10.0 * decade


def _um_per_pixel(viewer) -> float:
    """Scene units (µm) covered by one screen pixel along X."""
    a = viewer.mapToScene(QPoint(0, 0))
    b = viewer.mapToScene(QPoint(200, 0))
    return abs(b.x() - a.x()) / 200.0


class ViewerHud(QWidget):
    """
    Transparent overlay with corner brackets, workspace label, coordinates
    and a scale bar. Sits above the QGraphicsView; mouse events pass through.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("background: transparent;")

        # Clickable HUD controls live in a sibling widget (see ViewerHudControls),
        # but follow this overlay's visibility.
        self.controls: ViewerHudControls | None = None

        self._workspace = "CONFIG"
        self._coords = (0.0, 0.0)
        self._scale_um = 100.0
        self._scale_px = _TARGET_BAR_PX

        self._tl = make_hud_label(self)

        self._tr = make_hud_label(self)

        self._scale_lbl = make_hud_label(self)
        self._scale_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._refresh_labels()

    def setVisible(self, visible: bool) -> None:  # noqa: N802 (Qt override)
        super().setVisible(visible)
        if self.controls is not None:
            self.controls.setVisible(visible)

    def set_workspace(self, name: str) -> None:
        self._workspace = name.upper()
        self._refresh_labels()

    def set_coords(self, x: float, y: float) -> None:
        self._coords = (x, y)
        self._refresh_labels()

    def set_scale(self, scale_um: float, scale_px: float) -> None:
        self._scale_um = scale_um
        self._scale_px = max(20.0, min(scale_px, 160.0))
        um_text = f"{int(scale_um)}" if scale_um == int(scale_um) else f"{scale_um:g}"
        self._scale_lbl.setText(f"{um_text} µm")
        self._reposition()
        self.update()

    def _scale_bar_rect(self) -> tuple[int, int, int, int]:
        """Return (x, y, width, height) of the painted scale bar."""
        m = LABEL_INSET
        self._scale_lbl.adjustSize()
        label_h = self._scale_lbl.height()
        bar_w = int(self._scale_px)
        bar_h = 4
        gap = 4
        x = max(m, self.width() - m - bar_w)
        y = max(m, self.height() - m - label_h - gap - bar_h)
        return x, y, bar_w, bar_h

    def _refresh_labels(self) -> None:
        self._tl.setText(f"VIEWER · {self._workspace}")
        x, y = self._coords
        self._tr.setText(f"X {x:+.1f}  Y {y:+.1f} µm")
        self._reposition()

    def _reposition(self) -> None:
        m = LABEL_INSET
        self._tl.move(m, m)
        self._tl.adjustSize()
        self._tr.adjustSize()
        self._tr.move(max(m, self.width() - self._tr.width() - m), m)
        self._scale_lbl.adjustSize()
        self._scale_lbl.move(
            max(m, self.width() - self._scale_lbl.width() - m),
            max(m, self.height() - m - self._scale_lbl.height()),
        )

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        super().resizeEvent(a0)
        self._reposition()

    def paintEvent(self, a0: QPaintEvent | None) -> None:
        painter = QPainter(self)
        w, h = self.width(), self.height()
        paint_corner_brackets(painter, w, h)

        # Scale bar (drawn, not a child widget — avoids layout/visibility issues)
        bx, by, bw, bh = self._scale_bar_rect()
        painter.fillRect(bx, by, bw, bh, _SCALE_COLOR)

        painter.end()


class ViewerHudControls(QWidget):
    """
    Clickable HUD controls drawn over the viewer.

    Kept out of :class:`ViewerHud`: that overlay is transparent for mouse
    events, an attribute Qt also applies to child widgets.
    """

    _ACTION_SETTING = "newui/pi_joystick_action"
    _ACTIONS = {
        "none": ("Nothing", "circle"),
        "magic_focus": ("Run magic focus", "scan-eye"),
        "toggle_laser": ("Toggle laser(s)", "zap"),
        "toggle_joystick": ("Toggle joystick", "move-3d"),
        "toggle_light": ("Toggle light", "lightbulb"),
    }

    def __init__(
        self,
        viewer: "Viewer",
        instruments: Instruments,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._viewer = viewer
        self._instruments = instruments

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)

        self._follow_btn = self._add_button(
            icon_name="locate-fixed",
            tooltip="Keep the view centered on the focused item (C)",
            checkable=True,
        )
        self._follow_btn.toggled.connect(self._on_follow_toggled)

        self._add_separator()

        self._add_button(
            icon_name="zoom-out", tooltip="Zoom out (×0.5)"
        ).clicked.connect(lambda: self._apply_zoom(0.5))
        self._add_button(
            text="1:1", tooltip="Reset zoom to 1 µm per pixel"
        ).clicked.connect(self._reset_zoom)
        self._add_button(
            icon_name="zoom-in", tooltip="Zoom in (×2)"
        ).clicked.connect(lambda: self._apply_zoom(2.0))
        self._add_button(
            icon_name="maximize", tooltip="Fit every element in the view"
        ).clicked.connect(self._fit_all)

        self._add_separator()
        self._action_btn = self._add_button(
            icon_name="circle",
            tooltip="Choose the PI joystick action-button behaviour",
        )
        self._action_btn.setEnabled(
            isinstance(self._instruments.stage, PIStageInstrument)
        )
        self._build_action_menu()

        viewer.follow_stage_sight_changed.connect(self._follow_btn.setChecked)
        stage = instruments.stage
        if isinstance(stage, PIStageInstrument):
            stage.joystick_action_button_pressed.connect(
                self.trigger_joystick_action
            )
        self.sync()

    def _build_action_menu(self) -> None:
        menu = QMenu(self._action_btn)
        group = QActionGroup(menu)
        group.setExclusive(True)
        self._action_group = group
        self._action_menu = menu

        selected = str(
            QSettings("ledger", "laserstudio").value(
                self._ACTION_SETTING, "none"
            )
        )
        if selected not in self._ACTIONS:
            selected = "none"
        self._selected_action = selected

        for action_id, (label, icon_name) in self._ACTIONS.items():
            action = QAction(
                lucide.icon(icon_name, HUD_BTN_ICON_SIZE, theme.TEXT_MUTED),
                label,
                menu,
            )
            action.setData(action_id)
            action.setCheckable(True)
            action.setChecked(action_id == selected)
            if action_id == "magic_focus":
                action.setEnabled(self._instruments.focus_helper is not None)
            elif action_id == "toggle_laser":
                action.setEnabled(bool(self._instruments.lasers))
            elif action_id == "toggle_joystick":
                action.setEnabled(
                    isinstance(self._instruments.stage, PIStageInstrument)
                )
            elif action_id == "toggle_light":
                action.setEnabled(self._instruments.light is not None)
            group.addAction(action)
            menu.addAction(action)

        group.triggered.connect(self._on_action_selected)
        self._action_btn.setMenu(menu)
        self._refresh_action_button()

    def _on_action_selected(self, action: QAction) -> None:
        action_id = action.data()
        if not isinstance(action_id, str) or action_id not in self._ACTIONS:
            return
        self._selected_action = action_id
        QSettings("ledger", "laserstudio").setValue(
            self._ACTION_SETTING, action_id
        )
        self._refresh_action_button()

    def _refresh_action_button(self) -> None:
        label, icon_name = self._ACTIONS[self._selected_action]
        self._action_btn.setIcon(
            lucide.icon(icon_name, HUD_BTN_ICON_SIZE, theme.PURPLE)
        )
        self._action_btn.setToolTip(
            f"PI joystick action button: {label}. Click to choose another action."
        )

    def trigger_joystick_action(self) -> None:
        """Execute the action selected for PI joystick button 2."""
        try:
            if self._selected_action == "magic_focus":
                helper = self._instruments.focus_helper
                if helper is not None:
                    thread = helper.magic_focus()
                    if not thread.isRunning():
                        thread.start()
            elif self._selected_action == "toggle_laser":
                lasers = self._instruments.lasers
                turn_on = not any(bool(laser.on_off) for laser in lasers)
                for laser in lasers:
                    laser.on_off = turn_on
            elif self._selected_action == "toggle_joystick":
                stage = self._instruments.stage
                if isinstance(stage, PIStageInstrument):
                    stage.pi_joystick_enabled = not any(
                        stage.pi_joystick_enabled
                    )
            elif self._selected_action == "toggle_light":
                light = self._instruments.light
                if light is not None:
                    light.light = not bool(light.light)
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                "PI joystick action %s failed: %s",
                self._selected_action,
                exc,
            )

    def _add_button(
        self,
        *,
        tooltip: str,
        icon_name: str | None = None,
        text: str = "",
        checkable: bool = False,
    ) -> QPushButton:
        btn = QPushButton(text, self)
        btn.setCheckable(checkable)
        btn.setFixedSize(HUD_BTN_SIZE, HUD_BTN_SIZE)
        btn.setIconSize(QSize(HUD_BTN_ICON_SIZE, HUD_BTN_ICON_SIZE))
        btn.setStyleSheet(HUD_BTN_SS)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tooltip)
        if icon_name is not None:
            btn.setIcon(lucide.icon(icon_name, HUD_BTN_ICON_SIZE, theme.TEXT_MUTED))
        else:
            btn.setFont(theme.mono_font(LABEL_FONT_SIZE))
        self._layout.addWidget(btn)
        return btn

    def _add_separator(self) -> None:
        line = QFrame(self)
        line.setFixedSize(1, 16)
        line.setStyleSheet(f"background: {theme.BORDER};")
        self._layout.addWidget(line, 0, Qt.AlignmentFlag.AlignVCenter)

    def _apply_zoom(self, factor: float) -> None:
        self._viewer.set_auto_fit(False)
        self._viewer.zoom = self._viewer.zoom * factor
        self._refresh_scale()

    def _reset_zoom(self) -> None:
        self._viewer.set_auto_fit(False)
        del self._viewer.zoom
        self._refresh_scale()

    def _fit_all(self) -> None:
        self._viewer.set_auto_fit(False)
        self._viewer.reset_camera_to_visible_items()
        self._refresh_scale()

    def _refresh_scale(self) -> None:
        """Zooms done here bypass the viewport events the HUD listens to."""
        area = self.parent()
        if isinstance(area, ViewerArea):
            QTimer.singleShot(0, area.update_scale_from_viewer)

    def sync(self) -> None:
        """Align the controls with the viewer — call once a stage sight exists."""
        self._follow_btn.setEnabled(self._viewer.stage_sight is not None)
        self._follow_btn.setChecked(self._viewer.follow_stage_sight)
        self._refresh_follow_icon()

    def toggle_follow(self) -> None:
        """Flip the centering mode (bound to the viewer shortcut)."""
        if self._follow_btn.isEnabled():
            self._follow_btn.toggle()

    def _on_follow_toggled(self, checked: bool) -> None:
        self._viewer.follow_stage_sight = checked
        self._refresh_follow_icon()

    def _refresh_follow_icon(self) -> None:
        btn = self._follow_btn
        if not btn.isEnabled():
            color = theme.TEXT_DIM
        elif btn.isChecked():
            color = theme.PURPLE
        else:
            color = theme.TEXT_MUTED
        btn.setIcon(lucide.icon("locate-fixed", HUD_BTN_ICON_SIZE, color))


class ViewerArea(QWidget):
    """Viewer widget with a HUD overlay on top."""

    def __init__(
        self,
        instruments: Instruments,
        parent: QWidget | None = None,
    ) -> None:
        """
        :param instruments: Instruments model, forwarded to the Viewer.
        :param parent: Parent widget.
        """
        super().__init__(parent)
        scans = instruments.scans
        annotations = instruments.annotations

        self.setObjectName("ls-viewer-area")
        self.setStyleSheet(f"QWidget#ls-viewer-area {{ background: {theme.BG_MAIN}; }}")

        from ..viewer import Viewer

        self.viewer = Viewer(
            self,
            scans=scans,
            annotations=annotations,
        )
        self.hud = ViewerHud(self)
        self.controls = ViewerHudControls(self.viewer, instruments, self)
        self.hud.controls = self.controls
        self._distortion_overlay = None

        vp = self.viewer.viewport()
        if vp is not None:
            self._scale_sync = _ViewerScaleSync(self)
            vp.installEventFilter(self._scale_sync)

        self.viewer.mouse_moved.connect(self.hud.set_coords)

    def fit_view(self) -> None:
        """Frame the stage sight, or the full scene when a reference image exists."""
        self.viewer.schedule_fit_view()
        QTimer.singleShot(0, self.update_scale_from_viewer)

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        super().resizeEvent(a0)
        self.viewer.setGeometry(self.rect())
        self.hud.setGeometry(self.rect())
        self._reposition_controls()
        if self._distortion_overlay is not None:
            self._distortion_overlay.setGeometry(self.rect())
            if self._distortion_overlay.isVisible():
                self._distortion_overlay.raise_()
            else:
                self._raise_hud()
        else:
            self._raise_hud()
        QTimer.singleShot(0, self.update_scale_from_viewer)

    def _raise_hud(self) -> None:
        self.hud.raise_()
        self.controls.raise_()

    def _reposition_controls(self) -> None:
        """Park the HUD controls in the bottom-left corner, inside the brackets."""
        self.controls.adjustSize()
        self.controls.move(
            LABEL_INSET,
            max(0, self.height() - LABEL_INSET - self.controls.height()),
        )

    def showEvent(self, a0: QShowEvent | None) -> None:
        super().showEvent(a0)
        # The stage sight is added after construction, so the follow control
        # only learns whether it can be enabled here.
        self.controls.sync()
        self.fit_view()

    def show_distortion_overlay(self):
        from .distortion_overlay import DistortionOverlay

        if self._distortion_overlay is None:
            self._distortion_overlay = DistortionOverlay(self.viewer, self)
        self._distortion_overlay.setGeometry(self.rect())
        self.hud.hide()
        self._distortion_overlay.open()
        self._distortion_overlay.raise_()
        return self._distortion_overlay

    def update_scale_from_viewer(self) -> None:
        um_per_px = _um_per_pixel(self.viewer)
        if um_per_px <= 0:
            return
        bar_um = _nice_scale(_TARGET_BAR_PX * um_per_px)
        bar_px = bar_um / um_per_px
        self.hud.set_scale(bar_um, bar_px)


class _ViewerScaleSync(QObject):
    """Refresh the HUD scale bar when the viewer zoom or size changes."""

    def __init__(self, area: ViewerArea) -> None:
        super().__init__(area)
        self._area = area

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if a0 is None or a1 is None:
            return False
        if a1.type() in (QEvent.Type.Wheel, QEvent.Type.Resize):
            self._area.update_scale_from_viewer()
        return False
