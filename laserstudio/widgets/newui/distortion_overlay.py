"""Fullscreen overlay for reference-image distortion alignment."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...utils.background_align import BackgroundPin
from ..keyboardbox import Direction
from ..stagesight import StageSightViewer
from . import lucide, theme

if TYPE_CHECKING:
    from ..viewer import Viewer


@dataclass
class _WorkingPin:
    pin: BackgroundPin
    stage_label: str
    ref_label: str


class _ReferenceImagePane(QWidget):
    """Clickable reference image with fiducial markers."""

    clicked_px = pyqtSignal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setStyleSheet(f"background: {theme.BG_MAIN}; border: none;")
        self._pixmap: QPixmap | None = None
        self._markers: list[tuple[float, float]] = []  # normalized u,v

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap
        self._markers.clear()
        self.update()

    def set_markers(self, markers: list[tuple[float, float]]) -> None:
        self._markers = markers
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(theme.BG_MAIN))
        if self._pixmap is None or self._pixmap.isNull():
            painter.setPen(QColor(theme.TEXT_DIM))
            painter.drawText(
                self.rect(),
                int(Qt.AlignmentFlag.AlignCenter),
                "No reference image loaded",
            )
            painter.end()
            return

        pix = self._pixmap
        area = self.rect().adjusted(8, 8, -8, -8)
        scaled = pix.scaled(
            area.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = area.x() + (area.width() - scaled.width()) // 2
        y = area.y() + (area.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        self._img_rect = (x, y, scaled.width(), scaled.height())

        for i, (u, v) in enumerate(self._markers):
            mx = x + u * scaled.width()
            my = y + v * scaled.height()
            pen = QPen(QColor(theme.PURPLE))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(QColor(theme.PURPLE_BG))
            painter.drawEllipse(QPointF(mx, my), 8, 8)
            painter.setPen(QColor(theme.PURPLE))
            painter.drawText(int(mx + 10), int(my + 4), f"F{i + 1}")

        painter.end()

    def _map_click(self, pos) -> tuple[float, float] | None:
        if self._pixmap is None or self._pixmap.isNull():
            return None
        if not hasattr(self, "_img_rect"):
            return None
        x, y, w, h = self._img_rect
        if w <= 0 or h <= 0:
            return None
        lx, ly = pos.x() - x, pos.y() - y
        if lx < 0 or ly < 0 or lx > w or ly > h:
            return None
        u, v = lx / w, ly / h
        px = u * self._pixmap.width()
        py = v * self._pixmap.height()
        return px, py

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is None or event.button() != Qt.MouseButton.LeftButton:
            return
        mapped = self._map_click(event.position())
        if mapped is not None:
            self.clicked_px.emit(mapped[0], mapped[1])
        event.accept()


class _PinRow(QWidget):
    removed = pyqtSignal(int)
    stage_refreshed = pyqtSignal(int)

    def __init__(self, index: int, pin: _WorkingPin, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._index = index
        self.setStyleSheet(
            f"background: {theme.BG_CARD}; border: 1px solid {theme.BORDER};"
            " border-radius: 5px;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        lbl = QLabel(f"P{index + 1}")
        lbl.setStyleSheet(
            f"color: {theme.PURPLE}; font-family: monospace; font-size: 10px;"
            " background: transparent; font-weight: 700;"
        )
        header.addWidget(lbl)
        header.addStretch()
        rm = QPushButton()
        rm.setFixedSize(24, 24)
        rm.setIcon(lucide.icon("trash-2", 12, theme.TEXT_DIM))
        rm.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid"
            f" {theme.BORDER}; border-radius: 5px; }}"
            "QPushButton:hover {"
            "  color: #F04F52;"
            "  border-color: rgba(240,79,82,0.4);"
            "  background: rgba(240,79,82,0.08);"
            "}"
        )
        rm.clicked.connect(lambda: self.removed.emit(self._index))
        header.addWidget(rm)
        layout.addLayout(header)

        ref = QLabel(pin.ref_label)
        ref.setStyleSheet(_MONO_MUTED)
        layout.addWidget(ref)

        stage = QLabel(pin.stage_label)
        stage.setStyleSheet(_MONO_VALUE)
        layout.addWidget(stage)

        refresh = QPushButton("Set current stage position")
        refresh.setIcon(lucide.icon("locate-fixed", 12, theme.TEXT_MUTED))
        refresh.setStyleSheet(theme.GHOST_BTN)
        refresh.clicked.connect(lambda: self.stage_refreshed.emit(self._index))
        layout.addWidget(refresh)

    def update_labels(self, pin: _WorkingPin) -> None:
        for child in self.findChildren(QLabel):
            if child.text().startswith("P"):
                continue
            if "," in child.text() or "scene" in child.text() or "µm" in child.text():
                if "µm" in child.text() or "scene" in child.text():
                    child.setText(pin.stage_label)
                else:
                    child.setText(pin.ref_label)


_MONO_MUTED = (
    f"color: {theme.TEXT_MUTED}; font-family: monospace; font-size: 10px;"
    " background: transparent;"
)
_MONO_VALUE = (
    f"color: {theme.TEXT}; font-family: monospace; font-size: 10px;"
    " background: transparent;"
)


class DistortionOverlay(QWidget):
    """Fullscreen alignment overlay on top of the spatial viewer."""

    applied = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, viewer: Viewer, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._viewer = viewer
        self._working: list[_WorkingPin] = []
        self._saved_transform = None
        self._stage = viewer.stage_sight.stage if viewer.stage_sight else None

        self.setObjectName("ls-distortion-overlay")
        self.setStyleSheet(
            f"QWidget#ls-distortion-overlay {{ background: rgba(6,6,7,0.96); }}"
        )
        self.hide()

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(6)
        ref_title = QLabel("REFERENCE IMAGE · CLICK THE FEATURE MATCHING THE STAGE POSITION")
        ref_title.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-family: monospace; font-size: 10px;"
            " letter-spacing: 1px; background: transparent;"
        )
        left.addWidget(ref_title)
        self._ref_pane = _ReferenceImagePane()
        self._ref_pane.setMinimumHeight(280)
        self._ref_pane.clicked_px.connect(self._add_pin)
        left.addWidget(self._ref_pane, stretch=1)
        body.addLayout(left, stretch=1)

        cam_col = QVBoxLayout()
        cam_col.setSpacing(6)
        cam_title = QLabel("CAMERA")
        cam_title.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-family: monospace; font-size: 10px;"
            " letter-spacing: 1px; background: transparent;"
        )
        cam_col.addWidget(cam_title)
        self._camera_view: StageSightViewer | None = None
        if viewer.stage_sight is not None:
            self._camera_view = StageSightViewer(viewer.stage_sight, self)
            self._camera_view.setStyleSheet(f"background: {theme.BG_MAIN}; border: none;")
            self._camera_view.setMinimumHeight(280)
            cam_col.addWidget(self._camera_view, stretch=1)
        else:
            cam_col.addWidget(self._placeholder("No camera available"), stretch=1)
        body.addLayout(cam_col, stretch=1)

        body.addWidget(self._build_sidebar())
        root.addLayout(body, stretch=1)
        root.addWidget(self._build_footer())

        if self._stage is not None:
            self._stage.position_changed.connect(self._refresh_stage_readout)

    @staticmethod
    def _placeholder(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px;")
        return lbl

    def _build_header(self) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Distortion — Quad-to-Quad alignment")
        title.setStyleSheet(
            f"color: {theme.TEXT}; font-family: 'Brut Grotesque'; font-weight: 700;"
            " font-size: 15px; background: transparent;"
        )
        layout.addWidget(title)
        layout.addStretch()

        self._status_badge = QLabel("0 / 3 POINTS")
        self._status_badge.setStyleSheet(
            "font-family: monospace; font-size: 10px; letter-spacing: 0.06em;"
            f" color: {theme.ACCENT}; border: 1px solid {theme.ACCENT};"
            " border-radius: 20px; padding: 3px 11px; background: transparent;"
        )
        layout.addWidget(self._status_badge)

        close_btn = QPushButton()
        close_btn.setFixedSize(30, 30)
        close_btn.setIcon(lucide.icon("x", 16, theme.TEXT_MUTED))
        close_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.05); border: 1px solid"
            f" {theme.BORDER}; border-radius: 5px; }}"
            "QPushButton:hover { background: rgba(255,255,255,0.09); }"
        )
        close_btn.clicked.connect(self._cancel)
        layout.addWidget(close_btn)
        return row

    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        side.setFixedWidth(260)
        side.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(side)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        stage_box = QWidget()
        stage_box.setStyleSheet(
            f"background: {theme.BG_CARD}; border: 1px solid {theme.BORDER};"
            " border-radius: 5px;"
        )
        stage_layout = QVBoxLayout(stage_box)
        stage_layout.setContentsMargins(10, 10, 10, 10)
        stage_layout.setSpacing(6)

        self._stage_title = QLabel("STAGE")
        self._stage_title.setStyleSheet(_MONO_MUTED)
        stage_layout.addWidget(self._stage_title)

        self._stage_readout = QLabel("—")
        self._stage_readout.setStyleSheet(_MONO_VALUE)
        stage_layout.addWidget(self._stage_readout)
        layout.addWidget(stage_box)

        if self._stage is not None:
            from ..workspace.settingsworkspace import DpadWidget

            self._dpad = DpadWidget(self._stage, include_home=False)
            layout.addWidget(self._dpad)
        else:
            hint = QLabel(
                "Scene positioning — jog the view using Positioning,\n"
                "then click matching features on the reference image."
            )
            hint.setWordWrap(True)
            hint.setStyleSheet(
                f"color: {theme.TEXT_DIM}; font-size: 10px; background: transparent;"
            )
            layout.addWidget(hint)

        pts_title = QLabel("MATCHING POINTS")
        pts_title.setStyleSheet(_MONO_MUTED)
        layout.addWidget(pts_title)

        self._pins_container = QVBoxLayout()
        self._pins_container.setSpacing(6)
        layout.addLayout(self._pins_container)

        self._empty_pins = QLabel("NO POINTS YET")
        self._empty_pins.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_pins.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-family: monospace; font-size: 10px;"
            " border: 1px dashed rgba(255,255,255,0.12); border-radius: 6px;"
            " padding: 14px; background: transparent;"
        )
        layout.addWidget(self._empty_pins)

        self._hint = QLabel(
            "Jog the stage to aim the camera at a feature, then click the "
            "matching point on the reference image."
        )
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 11px; background: transparent;"
        )
        layout.addWidget(self._hint)
        layout.addStretch()
        return side

    def _build_footer(self) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setStyleSheet(theme.GHOST_BTN)
        self._cancel_btn.clicked.connect(self._cancel)
        layout.addWidget(self._cancel_btn)

        layout.addStretch()

        self._apply_btn = QPushButton("Apply distortion")
        self._apply_btn.setIcon(lucide.icon("check", 14, theme.GREEN))
        self._apply_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(110,200,92,0.14); color: {theme.GREEN};"
            " border: 1px solid rgba(110,200,92,0.5); border-radius: 6px;"
            " font-family: 'Brut Grotesque'; font-size: 12px; font-weight: 700;"
            f" padding: 10px 14px; }}"
            "QPushButton:disabled {"
            f"  color: {theme.TEXT_DIM};"
            "  background: rgba(255,255,255,0.03);"
            "  border-color: rgba(255,255,255,0.08);"
            "}"
        )
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._apply)
        layout.addWidget(self._apply_btn)
        return row

    def open(self) -> None:
        viewer = self._viewer
        if not viewer.has_background_picture:
            return
        pic = viewer.background_pixmap()
        self._ref_pane.set_pixmap(pic)
        if self._camera_view is not None:
            self._camera_view.reset_camera()
        self._working.clear()
        self._saved_transform = viewer.background_picture_transform()
        self._rebuild_pin_rows()
        self._refresh_stage_readout()
        self._sync_preview()
        self.show()
        self.raise_()

    def _format_stage_label(self, pin: BackgroundPin | None = None) -> str:
        if pin is not None:
            sx, sy = pin.stage_xy
        else:
            sx, sy, unit = self._viewer.background_stage_coords()
            return f"X {sx:+.1f}  Y {sy:+.1f} {unit}"
        _, _, unit = self._viewer.background_stage_coords()
        return f"X {sx:+.1f}  Y {sy:+.1f} {unit}"

    def _format_ref_label(self, pin: BackgroundPin) -> str:
        px, py = pin.image_px
        return f"ref {px:.0f}, {py:.0f} px"

    def _refresh_stage_readout(self, *_args) -> None:
        sx, sy, unit = self._viewer.background_stage_coords()
        title = "STAGE" if unit == "µm" else "SCENE"
        self._stage_title.setText(title)
        self._stage_readout.setText(f"X {sx:+.1f}  Y {sy:+.1f} {unit}")

    def _add_pin(self, px: float, py: float) -> None:
        if len(self._working) >= 3:
            return
        bg_pin = self._viewer.capture_background_pin((px, py))
        wp = _WorkingPin(
            pin=bg_pin,
            stage_label=self._format_stage_label(bg_pin),
            ref_label=self._format_ref_label(bg_pin),
        )
        self._working.append(wp)
        self._rebuild_pin_rows()
        self._sync_preview()

    def _remove_pin(self, index: int) -> None:
        if index < 0 or index >= len(self._working):
            return
        del self._working[index]
        self._rebuild_pin_rows()
        self._sync_preview()

    def _refresh_pin_stage(self, index: int) -> None:
        if index < 0 or index >= len(self._working):
            return
        wp = self._working[index]
        new_pin = self._viewer.capture_background_pin(wp.pin.image_px)
        self._working[index] = _WorkingPin(
            pin=new_pin,
            stage_label=self._format_stage_label(new_pin),
            ref_label=self._format_ref_label(new_pin),
        )
        self._rebuild_pin_rows()
        self._sync_preview()

    def _rebuild_pin_rows(self) -> None:
        while self._pins_container.count():
            item = self._pins_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        pix = self._viewer.background_pixmap()
        markers: list[tuple[float, float]] = []
        if pix is not None and not pix.isNull():
            pw, ph = pix.width(), pix.height()
            for wp in self._working:
                markers.append((wp.pin.image_px[0] / pw, wp.pin.image_px[1] / ph))
        self._ref_pane.set_markers(markers)

        has_pins = bool(self._working)
        self._empty_pins.setVisible(not has_pins)
        for i, wp in enumerate(self._working):
            row = _PinRow(i, wp)
            row.removed.connect(self._remove_pin)
            row.stage_refreshed.connect(self._refresh_pin_stage)
            self._pins_container.addWidget(row)

        n = len(self._working)
        valid = n == 3
        status = f"{n} / 3 POINTS" + (" · VALID" if valid else "")
        color = theme.GREEN if valid else theme.ACCENT
        self._status_badge.setText(status)
        self._status_badge.setStyleSheet(
            "font-family: monospace; font-size: 10px; letter-spacing: 0.06em;"
            f" color: {color}; border: 1px solid {color};"
            " border-radius: 20px; padding: 3px 11px; background: transparent;"
        )
        self._apply_btn.setEnabled(valid)
        if valid:
            self._hint.setText(
                "Transform preview active — review the viewer, then Apply."
            )
        elif n == 0:
            self._hint.setText(
                "Jog the stage to aim the camera at a feature, then click the "
                "matching point on the reference image."
            )
        else:
            self._hint.setText(
                f"{n} / 3 points — add {3 - n} more to preview the transform."
            )

    def _sync_preview(self) -> None:
        viewer = self._viewer
        if len(self._working) == 3:
            pins = [wp.pin for wp in self._working]
            viewer.preview_background_alignment(pins)
        else:
            viewer.restore_background_transform(self._saved_transform)

    def _apply(self) -> None:
        if len(self._working) != 3:
            return
        pins = [wp.pin for wp in self._working]
        if self._viewer.commit_background_alignment(pins):
            self._saved_transform = self._viewer.background_picture_transform()
            self.hide()
            self.applied.emit()

    def _cancel(self) -> None:
        self._viewer.restore_background_transform(self._saved_transform)
        self._working.clear()
        self.hide()
        self.cancelled.emit()
