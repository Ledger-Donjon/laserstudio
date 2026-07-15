"""HUD overlay drawn on top of the spatial viewer."""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QLabel, QWidget

from . import theme

_BRACKET = QColor(255, 255, 255, 115)  # rgba(255,255,255,0.45)
_SCALE_COLOR = QColor(theme.TEXT_MUTED)
_INSET = 14
_BRACKET_LEN = 16
_TARGET_BAR_PX = 46.0


def _nice_scale(um: float) -> float:
    """Pick a round scale-bar length in µm."""
    for val in (10, 20, 50, 100, 200, 500, 1000, 2000, 5000):
        if val >= um:
            return float(val)
    return float(int(um / 1000 + 1) * 1000)


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

        self._workspace = "CONFIG"
        self._coords = (0.0, 0.0)
        self._scale_um = 100.0
        self._scale_px = _TARGET_BAR_PX

        self._tl = QLabel(self)
        self._tl.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-family: monospace; font-size: 10px;"
            " background: transparent;"
        )

        self._tr = QLabel(self)
        self._tr.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-family: monospace; font-size: 10px;"
            " background: transparent;"
        )

        self._scale_lbl = QLabel(self)
        self._scale_lbl.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-family: monospace; font-size: 10px;"
            " background: transparent;"
        )
        self._scale_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._refresh_labels()

    def set_workspace(self, name: str) -> None:
        self._workspace = name.upper()
        self._refresh_labels()

    def set_coords(self, x: float, y: float) -> None:
        self._coords = (x, y)
        self._refresh_labels()

    def set_scale(self, scale_um: float, scale_px: float) -> None:
        self._scale_um = scale_um
        self._scale_px = max(20.0, min(scale_px, 160.0))
        um_text = (
            f"{int(scale_um)}"
            if scale_um == int(scale_um)
            else f"{scale_um:g}"
        )
        self._scale_lbl.setText(f"{um_text} µm")
        self._reposition()
        self.update()

    def _scale_bar_rect(self) -> tuple[int, int, int, int]:
        """Return (x, y, width, height) of the painted scale bar."""
        m = _INSET + 4
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
        m = _INSET + 4
        self._tl.move(m, m)
        self._tl.adjustSize()
        self._tr.adjustSize()
        self._tr.move(max(m, self.width() - self._tr.width() - m), m)
        self._scale_lbl.adjustSize()
        self._scale_lbl.move(
            max(m, self.width() - self._scale_lbl.width() - m),
            max(m, self.height() - m - self._scale_lbl.height()),
        )

    def resizeEvent(self, a0) -> None:  # noqa: N802
        super().resizeEvent(a0)
        self._reposition()

    def paintEvent(self, a0) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(_BRACKET)
        pen.setWidth(1)
        painter.setPen(pen)

        w, h = self.width(), self.height()
        inset = _INSET
        blen = _BRACKET_LEN

        # Corner brackets
        painter.drawLine(inset, inset, inset + blen, inset)
        painter.drawLine(inset, inset, inset, inset + blen)
        painter.drawLine(w - inset, inset, w - inset - blen, inset)
        painter.drawLine(w - inset, inset, w - inset, inset + blen)
        painter.drawLine(inset, h - inset, inset + blen, h - inset)
        painter.drawLine(inset, h - inset, inset, h - inset - blen)
        painter.drawLine(w - inset, h - inset, w - inset - blen, h - inset)
        painter.drawLine(w - inset, h - inset, w - inset, h - inset - blen)

        # Scale bar (drawn, not a child widget — avoids layout/visibility issues)
        bx, by, bw, bh = self._scale_bar_rect()
        painter.fillRect(bx, by, bw, bh, _SCALE_COLOR)

        painter.end()


class ViewerArea(QWidget):
    """Viewer widget with a HUD overlay on top."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ls-viewer-area")
        self.setStyleSheet(f"QWidget#ls-viewer-area {{ background: {theme.BG_MAIN}; }}")

        from ..viewer import Viewer

        self.viewer = Viewer(self)
        self.hud = ViewerHud(self)
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

    def resizeEvent(self, a0) -> None:  # noqa: N802
        super().resizeEvent(a0)
        self.viewer.setGeometry(self.rect())
        self.hud.setGeometry(self.rect())
        if self._distortion_overlay is not None:
            self._distortion_overlay.setGeometry(self.rect())
            if self._distortion_overlay.isVisible():
                self._distortion_overlay.raise_()
            else:
                self.hud.raise_()
        else:
            self.hud.raise_()
        QTimer.singleShot(0, self.update_scale_from_viewer)

    def showEvent(self, a0) -> None:  # noqa: N802
        super().showEvent(a0)
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

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if event.type() in (QEvent.Type.Wheel, QEvent.Type.Resize):
            self._area.update_scale_from_viewer()
        return False

