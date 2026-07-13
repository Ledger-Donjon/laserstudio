"""Fullscreen overlay for reference-image distortion alignment."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...instruments.stage import StageInstrument, Vector
from ...utils.background_align import BackgroundPin
from ..keyboardbox import Direction
from . import lucide, theme

if TYPE_CHECKING:
    from ...instruments.camera import CameraInstrument
    from ..viewer import Viewer

_SIDEBAR_W = 300
_CAMERA_BLUE = "#4A9EFF"
_CAMERA_BG = "#131217"
_MODAL_CELL = 32
_MODAL_GAP = 4
_FOOTER_H = 52

_CARD_SS = (
    f"QFrame#ls-dist-viewport {{"
    f" background: {theme.BG_MAIN};"
    f" border: 1px solid {theme.BORDER};"
    " border-radius: 8px;"
    " }"
)

_MODAL_DPAD_SS = f"""
QPushButton {{
    background: rgba(255,255,255,0.05);
    color: {theme.TEXT};
    border: 1px solid {theme.BORDER};
    border-radius: 5px;
    min-width: {_MODAL_CELL}px;
    max-width: {_MODAL_CELL}px;
    min-height: {_MODAL_CELL}px;
    max-height: {_MODAL_CELL}px;
    padding: 0;
}}
QPushButton:hover {{ background: rgba(255,255,255,0.09); }}
"""

_MODAL_Z_SS = f"""
QPushButton {{
    background: {theme.PURPLE_BG};
    color: {theme.PURPLE};
    border: 1px solid {theme.PURPLE_BORDER};
    border-radius: 5px;
    font-family: monospace;
    font-size: 10px;
    min-width: {_MODAL_CELL}px;
    max-width: {_MODAL_CELL}px;
    min-height: {_MODAL_CELL}px;
    max-height: {_MODAL_CELL}px;
    padding: 0;
}}
QPushButton:hover {{ background: rgba(212,160,255,0.20); }}
"""

_MONO_MUTED = (
    f"color: {theme.TEXT_MUTED}; font-family: monospace; font-size: 10px;"
    " background: transparent;"
)
_MONO_VALUE = (
    f"color: {theme.TEXT}; font-family: monospace; font-size: 10px;"
    " background: transparent;"
)
_EYEBROW = (
    f"color: {theme.TEXT_DIM}; font-family: monospace; font-size: 10px;"
    " letter-spacing: 1px; background: transparent;"
)


@dataclass
class _WorkingPin:
    pin: BackgroundPin
    stage_label: str
    ref_label: str


class _AspectRatioHost(QWidget):
    """Container that keeps a fixed width-to-height ratio (design: 4:3 camera)."""

    def __init__(self, ratio_w: int, ratio_h: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ratio = ratio_w / ratio_h
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return max(1, int(width / self._ratio))

    def sizeHint(self) -> QSize:
        return QSize(280, int(280 / self._ratio))


_ZOOM_MIN = 0.25
_ZOOM_MAX = 32.0
_PAN_DRAG_BUTTONS = (
    Qt.MouseButton.MiddleButton,
    Qt.MouseButton.RightButton,
)


class _ZoomPanViewport(QWidget):
    """Pixmap viewport with wheel zoom and drag-to-pan."""

    def __init__(
        self,
        *,
        cover: bool = False,
        padding: int = 0,
        bg_color: str = "#000000",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cover = cover
        self._padding = padding
        self._bg_color = bg_color
        self._pixmap: QPixmap | None = None
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._panning = False
        self._pan_anchor = QPointF()
        self._pan_origin = QPointF()
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap
        self.reset_view()

    def reset_view(self) -> None:
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self.update()

    def _content_area(self) -> QRect:
        pad = self._padding
        return self.rect().adjusted(pad, pad, -pad, -pad)

    def _image_rect(self) -> tuple[float, float, float, float] | None:
        if self._pixmap is None or self._pixmap.isNull():
            return None
        area = self._content_area()
        if area.width() <= 0 or area.height() <= 0:
            return None

        pw, ph = self._pixmap.width(), self._pixmap.height()
        if pw <= 0 or ph <= 0:
            return None

        if self._cover:
            fit_scale = max(area.width() / pw, area.height() / ph)
        else:
            fit_scale = min(area.width() / pw, area.height() / ph)

        scale = fit_scale * self._zoom
        draw_w = pw * scale
        draw_h = ph * scale
        cx = area.x() + area.width() / 2 + self._pan.x()
        cy = area.y() + area.height() / 2 + self._pan.y()
        return (cx - draw_w / 2, cy - draw_h / 2, draw_w, draw_h)

    def _map_widget_to_normalized(self, pos: QPointF) -> tuple[float, float] | None:
        rect = self._image_rect()
        if rect is None:
            return None
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            return None
        lx, ly = pos.x() - x, pos.y() - y
        if lx < 0 or ly < 0 or lx > w or ly > h:
            return None
        return lx / w, ly / h

    def _begin_pan(self, pos: QPointF) -> None:
        self._panning = True
        self._pan_anchor = pos
        self._pan_origin = QPointF(self._pan)
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def _update_pan(self, pos: QPointF) -> None:
        if not self._panning:
            return
        delta = pos - self._pan_anchor
        self._pan = self._pan_origin + delta
        self.update()

    def _end_pan(self) -> None:
        self._panning = False
        self._restore_cursor()

    def _restore_cursor(self) -> None:
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def wheelEvent(self, event: QWheelEvent | None) -> None:  # type: ignore[override]
        if event is None or self._pixmap is None or self._pixmap.isNull():
            return

        rect = self._image_rect()
        if rect is None:
            return

        pos = event.position()
        x, y, w, h = rect
        u = (pos.x() - x) / w
        v = (pos.y() - y) / h

        zr = 2 ** (event.angleDelta().y() / (8 * 120))
        self._zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, self._zoom * zr))

        new_rect = self._image_rect()
        if new_rect is None:
            self.update()
            event.accept()
            return

        nx, ny, nw, nh = new_rect
        cx = pos.x() - u * nw + nw / 2
        cy = pos.y() - v * nh + nh / 2
        area = self._content_area()
        self._pan = QPointF(
            cx - (area.x() + area.width() / 2),
            cy - (area.y() + area.height() / 2),
        )
        self.update()
        event.accept()

    def mousePressEvent(self, event: QMouseEvent | None) -> None:  # type: ignore[override]
        if event is None:
            return
        if event.button() in _PAN_DRAG_BUTTONS:
            self._begin_pan(event.position())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:  # type: ignore[override]
        if event is None:
            return
        if self._panning:
            self._update_pan(event.position())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:  # type: ignore[override]
        if event is None:
            return
        if event.button() in _PAN_DRAG_BUTTONS and self._panning:
            self._end_pan()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _paint_overlay(
        self,
        painter: QPainter,
        img_rect: tuple[float, float, float, float] | None,
    ) -> None:
        return

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(self._bg_color))
        img_rect = self._image_rect()
        if self._pixmap is not None and not self._pixmap.isNull() and img_rect is not None:
            x, y, w, h = img_rect
            painter.drawPixmap(
                QRectF(x, y, w, h),
                self._pixmap,
                QRectF(0, 0, self._pixmap.width(), self._pixmap.height()),
            )
        self._paint_overlay(painter, img_rect)
        painter.end()


class _CameraFeedPane(_ZoomPanViewport):
    """Live camera preview with design crosshair — does not steal stage_sight from viewer."""

    def __init__(
        self, camera: CameraInstrument | None, parent: QWidget | None = None
    ) -> None:
        super().__init__(cover=True, padding=0, bg_color=_CAMERA_BG, parent=parent)
        self._camera = camera
        if camera is not None:
            camera.new_image.connect(self._on_image)

    def _on_image(self, image: QImage) -> None:
        if self._pixmap is None:
            self.set_pixmap(QPixmap.fromImage(image.copy()))
        else:
            self._pixmap = QPixmap.fromImage(image.copy())
            self.update()

    def _restore_cursor(self) -> None:
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def _paint_overlay(
        self,
        painter: QPainter,
        img_rect: tuple[float, float, float, float] | None,
    ) -> None:
        cx, cy = self.width() / 2, self.height() / 2
        pen = QPen(QColor(_CAMERA_BLUE))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(int(cx - 20), int(cy), int(cx + 20), int(cy))
        painter.drawLine(int(cx), int(cy - 20), int(cx), int(cy + 20))
        painter.drawEllipse(QPointF(cx, cy), 9, 9)


class _ReferenceImagePane(_ZoomPanViewport):
    """Clickable reference image with fiducial markers."""

    clicked_px = pyqtSignal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(cover=False, padding=4, bg_color="#000000", parent=parent)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setStyleSheet("background: #000; border: none;")
        self._markers: list[tuple[float, float]] = []

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        self._markers.clear()
        super().set_pixmap(pixmap)

    def set_markers(self, markers: list[tuple[float, float]]) -> None:
        self._markers = markers
        self.update()

    def _restore_cursor(self) -> None:
        self.setCursor(Qt.CursorShape.CrossCursor)

    def _paint_overlay(
        self,
        painter: QPainter,
        img_rect: tuple[float, float, float, float] | None,
    ) -> None:
        if img_rect is None or self._pixmap is None or self._pixmap.isNull():
            if self._pixmap is None or self._pixmap.isNull():
                painter.setPen(QColor(theme.TEXT_DIM))
                painter.drawText(
                    self.rect(),
                    int(Qt.AlignmentFlag.AlignCenter),
                    "No reference image loaded",
                )
            return

        x, y, w, h = img_rect
        for i, (u, v) in enumerate(self._markers):
            mx = x + u * w
            my = y + v * h
            pen = QPen(QColor(theme.PURPLE))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(QColor(theme.PURPLE_BG))
            painter.drawEllipse(QPointF(mx, my), 7, 7)
            painter.setPen(QColor(theme.PURPLE))
            painter.drawText(int(mx + 9), int(my + 4), f"F{i + 1}")

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        if event.button() in _PAN_DRAG_BUTTONS:
            super().mousePressEvent(event)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        mapped = self._map_click(event.position())
        if mapped is not None:
            self.clicked_px.emit(mapped[0], mapped[1])
        event.accept()

    def _map_click(self, pos: QPointF) -> tuple[float, float] | None:
        if self._pixmap is None or self._pixmap.isNull():
            return None
        norm = self._map_widget_to_normalized(pos)
        if norm is None:
            return None
        u, v = norm
        return u * self._pixmap.width(), v * self._pixmap.height()


class _ModalJogPanel(QWidget):
    """Compact 32 px D-pad + single STEP field for the alignment modal."""

    def __init__(self, stage: StageInstrument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._stage = stage
        self._num_axis = stage.num_axis
        self._step = 100.0
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        pad = QWidget()
        pad.setStyleSheet("background: transparent;")
        grid = QGridLayout(pad)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(_MODAL_GAP)
        grid.setVerticalSpacing(_MODAL_GAP)

        if self._num_axis > 1:
            grid.addWidget(self._arrow_btn("arrow-up", Direction.up), 0, 1)
        if self._num_axis > 0:
            grid.addWidget(self._arrow_btn("arrow-left", Direction.left), 1, 0)
            spacer = QWidget()
            spacer.setFixedSize(_MODAL_CELL, _MODAL_CELL)
            spacer.setStyleSheet("background: transparent;")
            grid.addWidget(spacer, 1, 1)
            grid.addWidget(self._arrow_btn("arrow-right", Direction.right), 1, 2)
        if self._num_axis > 1:
            grid.addWidget(self._arrow_btn("arrow-down", Direction.down), 2, 1)
        if self._num_axis > 2:
            grid.addWidget(self._z_btn("Z+", Direction.zup), 0, 2)
            grid.addWidget(self._z_btn("Z−", Direction.zdown), 2, 2)

        root.addWidget(pad, alignment=Qt.AlignmentFlag.AlignHCenter)

        step_row = QHBoxLayout()
        step_row.setSpacing(8)
        step_lbl = QLabel("STEP µm")
        step_lbl.setStyleSheet(_MONO_MUTED)
        step_row.addWidget(step_lbl)
        self._step_spin = QDoubleSpinBox()
        self._step_spin.setRange(0.1, 1_000_000)
        self._step_spin.setDecimals(1)
        self._step_spin.setValue(self._step)
        self._step_spin.setFixedHeight(theme.BTN_MIN_H)
        self._step_spin.setStyleSheet(
            f"background: {theme.BG_CARD}; color: {theme.TEXT};"
            f" border: 1px solid {theme.BORDER}; border-radius: 5px;"
            " font-family: monospace; font-size: 11px; padding: 0 8px;"
        )
        self._step_spin.valueChanged.connect(lambda v: setattr(self, "_step", float(v)))
        step_row.addWidget(self._step_spin, stretch=1)
        root.addLayout(step_row)

    def _arrow_btn(self, icon: str, direction: Direction) -> QPushButton:
        btn = QPushButton()
        btn.setIcon(lucide.icon(icon, 14, theme.TEXT))
        btn.setStyleSheet(_MODAL_DPAD_SS)
        btn.clicked.connect(lambda: self._move(direction))
        return btn

    def _z_btn(self, label: str, direction: Direction) -> QPushButton:
        btn = QPushButton(label)
        btn.setStyleSheet(_MODAL_Z_SS)
        btn.clicked.connect(lambda: self._move(direction))
        return btn

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

        displacement = self._step * factor
        if direction in (Direction.down, Direction.left, Direction.zdown):
            displacement *= -1

        position = self._stage.position
        position[axe] += displacement
        self._stage.move_to(position, wait=False)


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
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        header = QHBoxLayout()
        lbl = QLabel(f"P{index + 1}")
        lbl.setStyleSheet(
            f"color: {theme.PURPLE}; font-family: monospace; font-size: 10px;"
            " background: transparent; font-weight: 700;"
        )
        header.addWidget(lbl)
        header.addStretch()
        rm = QPushButton()
        rm.setFixedSize(22, 22)
        rm.setIcon(lucide.icon("trash-2", 11, theme.TEXT_DIM))
        rm.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid"
            f" {theme.BORDER}; border-radius: 4px; }}"
            "QPushButton:hover {"
            "  color: #F04F52; border-color: rgba(240,79,82,0.4);"
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
        refresh.setIcon(lucide.icon("locate-fixed", 11, theme.TEXT_MUTED))
        refresh.setStyleSheet(theme.GHOST_BTN)
        refresh.setFixedHeight(theme.BTN_MIN_H)
        refresh.clicked.connect(lambda: self.stage_refreshed.emit(self._index))
        layout.addWidget(refresh)


def _viewport_card(caption: str, viewport: QWidget) -> QFrame:
    card = QFrame()
    card.setObjectName("ls-dist-viewport")
    card.setStyleSheet(_CARD_SS)
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)
    title = QLabel(caption)
    title.setStyleSheet(_EYEBROW)
    title.setWordWrap(True)
    layout.addWidget(title)
    layout.addWidget(viewport, stretch=1)
    return card


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
        self.setStyleSheet(f"QWidget#ls-distortion-overlay {{ background: {theme.BG_ROOT}; }}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("ls-dist-shell")
        shell.setStyleSheet(
            f"QFrame#ls-dist-shell {{ background: {theme.BG_PANEL};"
            f" border: 1px solid {theme.BORDER}; border-radius: 10px; }}"
        )
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(14, 12, 14, 12)
        shell_layout.setSpacing(12)

        shell_layout.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(10)

        self._ref_pane = _ReferenceImagePane()
        self._ref_pane.clicked_px.connect(self._add_pin)
        body.addWidget(
            _viewport_card(
                "REFERENCE IMAGE · CLICK THE FEATURE MATCHING THE STAGE POSITION",
                self._ref_pane,
            ),
            stretch=16,
        )
        body.addWidget(self._build_sidebar())
        shell_layout.addLayout(body, stretch=1)

        shell_layout.addWidget(self._build_footer())
        outer.addWidget(shell)

        if self._stage is not None:
            self._stage.position_changed.connect(self._refresh_stage_readout)

        self.hide()

    def _build_header(self) -> QWidget:
        row = QWidget()
        row.setFixedHeight(36)
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

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
        close_btn.setFixedSize(28, 28)
        close_btn.setIcon(lucide.icon("x", 14, theme.TEXT_MUTED))
        close_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.05); border: 1px solid"
            f" {theme.BORDER}; border-radius: 5px; }}"
            "QPushButton:hover { background: rgba(255,255,255,0.09); }"
        )
        close_btn.clicked.connect(self._cancel)
        layout.addWidget(close_btn)
        return row

    def _build_sidebar(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setFixedWidth(_SIDEBAR_W)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        side = QWidget()
        side.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(side)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        cam_title = QLabel("CAMERA")
        cam_title.setStyleSheet(_EYEBROW)
        layout.addWidget(cam_title)

        cam_ratio = _AspectRatioHost(4, 3)
        cam_frame = QFrame(cam_ratio)
        cam_frame.setStyleSheet(
            f"QFrame {{ background: {_CAMERA_BG};"
            f" border: 1px solid rgba(74,158,255,0.55); border-radius: 6px; }}"
        )
        cam_layout = QVBoxLayout(cam_ratio)
        cam_layout.setContentsMargins(0, 0, 0, 0)
        cam_inner = QVBoxLayout(cam_frame)
        cam_inner.setContentsMargins(0, 0, 0, 0)
        camera = (
            self._viewer.stage_sight.camera
            if self._viewer.stage_sight is not None
            else None
        )
        self._camera_pane: _CameraFeedPane | None = None
        if camera is not None:
            self._camera_pane = _CameraFeedPane(camera, cam_frame)
            cam_inner.addWidget(self._camera_pane)
        else:
            ph = QLabel("No camera available")
            ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ph.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px;")
            cam_inner.addWidget(ph)
        cam_layout.addWidget(cam_frame)
        layout.addWidget(cam_ratio)

        stage_box = QFrame()
        stage_box.setObjectName("ls-dist-stage")
        stage_box.setStyleSheet(
            f"QFrame#ls-dist-stage {{ background: {theme.BG_CARD};"
            f" border: 1px solid {theme.BORDER}; border-radius: 5px; }}"
        )
        stage_layout = QVBoxLayout(stage_box)
        stage_layout.setContentsMargins(10, 8, 10, 8)
        stage_layout.setSpacing(4)
        self._stage_title = QLabel("STAGE")
        self._stage_title.setStyleSheet(_MONO_MUTED)
        stage_layout.addWidget(self._stage_title)
        self._stage_readout = QLabel("—")
        self._stage_readout.setStyleSheet(_MONO_VALUE)
        stage_layout.addWidget(self._stage_readout)
        layout.addWidget(stage_box)

        if self._stage is not None:
            layout.addWidget(_ModalJogPanel(self._stage))
        else:
            hint = QLabel(
                "Scene positioning — use the Positioning panel to move the "
                "view, then click features on the reference image."
            )
            hint.setWordWrap(True)
            hint.setStyleSheet(
                f"color: {theme.TEXT_DIM}; font-size: 10px; background: transparent;"
            )
            layout.addWidget(hint)

        pts_title = QLabel("MATCHING POINTS")
        pts_title.setStyleSheet(_MONO_MUTED)
        layout.addWidget(pts_title)

        self._pins_host = QWidget()
        self._pins_host.setStyleSheet("background: transparent;")
        self._pins_container = QVBoxLayout(self._pins_host)
        self._pins_container.setContentsMargins(0, 0, 0, 0)
        self._pins_container.setSpacing(6)
        layout.addWidget(self._pins_host)

        self._empty_pins = QLabel("NO POINTS YET")
        self._empty_pins.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_pins.setFixedHeight(48)
        self._empty_pins.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-family: monospace; font-size: 10px;"
            " border: 1px dashed rgba(255,255,255,0.12); border-radius: 6px;"
            " background: transparent;"
        )
        layout.addWidget(self._empty_pins)

        self._hint = QLabel(
            "Jog the stage to aim the camera at a feature, then click the "
            "matching point on the reference image. Wheel zooms; right or "
            "middle drag pans both views."
        )
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; background: transparent;"
        )
        layout.addWidget(self._hint)
        layout.addStretch(1)

        scroll.setWidget(side)
        self._side_scroll = scroll
        return scroll

    def _build_footer(self) -> QWidget:
        row = QWidget()
        row.setObjectName("ls-dist-footer")
        row.setFixedHeight(_FOOTER_H)
        row.setStyleSheet(
            f"QWidget#ls-dist-footer {{ background: {theme.BG_CARD};"
            f" border: 1px solid {theme.BORDER}; border-radius: 8px; }}"
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setFixedHeight(theme.BTN_MIN_H)
        self._cancel_btn.setStyleSheet(theme.GHOST_BTN)
        self._cancel_btn.clicked.connect(self._cancel)
        layout.addWidget(self._cancel_btn)

        layout.addStretch()

        self._apply_btn = QPushButton("Apply distortion")
        self._apply_btn.setFixedHeight(theme.BTN_MIN_H)
        self._apply_btn.setIcon(lucide.icon("check", 14, theme.GREEN))
        self._apply_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(110,200,92,0.14); color: {theme.GREEN};"
            " border: 1px solid rgba(110,200,92,0.5); border-radius: 6px;"
            " font-family: 'Brut Grotesque'; font-size: 12px; font-weight: 700;"
            " padding: 0 14px; }}"
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

    def _set_hud_visible(self, visible: bool) -> None:
        parent = self.parent()
        if parent is not None and hasattr(parent, "hud"):
            parent.hud.setVisible(visible)

    def hideEvent(self, event) -> None:  # type: ignore[override]
        self._set_hud_visible(True)
        super().hideEvent(event)

    def open(self) -> None:
        viewer = self._viewer
        if not viewer.has_background_picture:
            return
        self._ref_pane.set_pixmap(viewer.background_pixmap())
        if self._camera_pane is not None:
            self._camera_pane.reset_view()
        self._working.clear()
        self._saved_transform = viewer.background_picture_transform()
        self._rebuild_pin_rows()
        self._refresh_stage_readout()
        self._sync_preview()
        self._set_hud_visible(False)
        self.show()
        self.raise_()

    def _format_stage_label(self, pin: BackgroundPin | None = None) -> str:
        if pin is not None:
            sx, sy = pin.stage_xy
            unit = "µm" if self._stage is not None else "scene"
        else:
            sx, sy, unit = self._viewer.background_stage_coords()
        return f"X {sx:+.1f}  Y {sy:+.1f} {unit}"

    def _format_ref_label(self, pin: BackgroundPin) -> str:
        px, py = pin.image_px
        return f"ref {px:.0f}, {py:.0f} px"

    def _refresh_stage_readout(self, position: Vector | None = None) -> None:
        if position is not None:
            sx, sy = float(position[0]), float(position[1])
            unit = "µm"
        else:
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
                "matching point on the reference image. Wheel zooms; right or "
                "middle drag pans both views."
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
