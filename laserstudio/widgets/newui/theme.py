"""
Ledger design-system tokens and shared UI helpers for the new Laser Studio UI.

Colors, spacing and typography come from the official Ledger design system
handoff. Keeping them here (rather than in ``laserstudio_refonte``) lets both
the main window and the individual workspace panels share one source of truth
without a circular import.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QSplitterHandle,
    QVBoxLayout,
    QWidget,
)

from . import lucide

# ── Color tokens ───────────────────────────────────────────────────────────────
BG_ROOT = "#060607"
BG_MAIN = "#0A0A0A"
BG_PANEL = "#0C0C0D"
BG_TABS = "#131214"
BG_CARD = "#131214"
BORDER = "rgba(255,255,255,0.10)"
BORDER_SUBTLE = "rgba(255,255,255,0.08)"
BORDER_HOVER = "rgba(255,255,255,0.22)"
TEXT = "#F1F1F1"
TEXT_MUTED = "#A3A3A3"
TEXT_DIM = "#6A6A6A"
TAB_INACTIVE = "#8A8A8A"
ACCENT = "#FF5300"
PURPLE = "#D4A0FF"
PURPLE_BG = "rgba(212,160,255,0.12)"
PURPLE_BORDER = "rgba(212,160,255,0.40)"
GREEN = "#6EC85C"
GREEN_BG = "rgba(110,200,92,0.12)"

# Sidebar panel layout — vertical Minimum (never Maximum) prevents Qt from
# crushing controls when the column is resized.
PANEL_INNER = "ls-panel-inner"
SIDEBAR_MARGIN_H = 18
SCROLLBAR_WIDTH = 8
# Usable content in the 320 px design column: 320 − margins − scrollbar.
SIDEBAR_CONTENT_MIN = 320 - 2 * SIDEBAR_MARGIN_H - SCROLLBAR_WIDTH
SIDEBAR_MIN_WIDTH = SIDEBAR_CONTENT_MIN + 2 * SIDEBAR_MARGIN_H + SCROLLBAR_WIDTH
# Compact sidebar controls — design uses padding-only sizing (~28px total).
# Do not stack min-height + vertical padding (Qt doubles the effective height).
CONTROL_MIN_H = 28
BTN_MIN_H = 28

_SCROLLBAR_SS = f"""
QScrollBar:vertical {{
    background: transparent;
    width: {SCROLLBAR_WIDTH}px;
    margin: 6px 0;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.14);
    border-radius: 4px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(255, 255, 255, 0.24);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    border: none;
    background: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}
QScrollBar:horizontal {{
    height: 0;
}}
"""

SIDEBAR_SS = f"""
QStackedWidget#ls-sidebar {{
    background: {BG_PANEL};
}}
QStackedWidget#ls-sidebar QLineEdit,
QStackedWidget#ls-sidebar QComboBox,
QStackedWidget#ls-sidebar QSpinBox,
QStackedWidget#ls-sidebar QDoubleSpinBox {{
    min-height: 0;
    max-height: {CONTROL_MIN_H}px;
    padding: 5px 10px;
}}
QStackedWidget#ls-sidebar {_SCROLLBAR_SS}
"""


def scroll_area_stylesheet(*, background: str = BG_PANEL) -> str:
    """Stylesheet for sidebar scroll areas — thin dark scrollbar, no arrows."""
    return (
        f"QScrollArea {{ border: none; background: {background}; }}"
        f"{_SCROLLBAR_SS}"
    )


def setup_scroll_area(
    scroll: QScrollArea, *, background: str = BG_PANEL
) -> QScrollArea:
    """Configure a sidebar scroll area with consistent scrollbar styling."""
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setStyleSheet(scroll_area_stylesheet(background=background))
    return scroll

# ── Reusable stylesheets ─────────────────────────────────────────────────────
# Segmented-control tab: active = purple fill + black text (per design).
# Scoped under #ls-tabs-bg to override the global ledger QPushButton:checked rule.
TAB_SS = f"""
QWidget#ls-tabs-bg QPushButton {{
    background-color: transparent;
    color: {TAB_INACTIVE};
    border: none;
    border-radius: 6px;
    font-family: "Brut Grotesque";
    font-weight: 700;
    font-size: 13px;
    padding: 0 15px;
    min-height: 34px;
}}
QWidget#ls-tabs-bg QPushButton:hover {{
    background-color: rgba(255,255,255,0.06);
    color: {TEXT};
}}
QWidget#ls-tabs-bg QPushButton:checked {{
    background-color: {PURPLE};
    color: #0A0A0A;
}}
"""

GHOST_BTN = f"""
QPushButton {{
    background: rgba(255,255,255,0.05);
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 5px;
    font-family: "Brut Grotesque";
    font-size: 11px;
    padding: 6px 12px;
    min-height: 0;
    max-height: {BTN_MIN_H}px;
}}
QPushButton:hover {{
    background: rgba(255,255,255,0.09);
    color: white;
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    background: rgba(255,255,255,0.02);
    border-color: rgba(255,255,255,0.06);
}}
"""

PURPLE_BTN = f"""
QPushButton {{
    background: {PURPLE_BG};
    color: {PURPLE};
    border: 1px solid {PURPLE_BORDER};
    border-radius: 5px;
    font-family: "Brut Grotesque";
    font-size: 12px;
    padding: 6px 12px;
    min-height: 0;
    max-height: {BTN_MIN_H}px;
}}
QPushButton:hover {{
    background: rgba(212,160,255,0.20);
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    background: rgba(255,255,255,0.02);
    border-color: rgba(255,255,255,0.06);
}}
"""


# ── Parameter value formatting ────────────────────────────────────────────────
SKIP_PROPS = {"enable", "label"}

KEY_LABELS: dict[str, str] = {
    "type": "type",
    "refresh_interval_ms": "refresh interval",
    "spot_size_um": "spot size",
    "pixel_size_in_um": "pixel size",
    "num_axis": "axes",
    "unit_factor": "unit factor",
    "objective": "objective",
    "index": "device index",
    "width": "width",
    "height": "height",
}

_VALUE_FMT: dict[str, object] = {
    "refresh_interval_ms": lambda v: f"{v} ms",
    "spot_size_um": lambda v: f"{v} µm",
    "pixel_size_in_um": lambda v: (
        f"{v[0]} × {v[1]} µm" if isinstance(v, list) and len(v) == 2 else str(v)
    ),
    "objective": lambda v: f"{v}×",
    "width": lambda v: f"{v} px",
    "height": lambda v: f"{v} px",
}


def fmt_value(key: str, val: object) -> str:
    fmt = _VALUE_FMT.get(key)
    if fmt is not None:
        return fmt(val)  # type: ignore[operator]
    if isinstance(val, bool):
        return "Yes" if val else "No"
    if isinstance(val, list):
        return ", ".join(str(x) for x in val)
    if isinstance(val, float):
        return f"{val:g}"
    return str(val)


# ── Widget helpers ────────────────────────────────────────────────────────────
def eyebrow(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {TEXT_DIM}; font-family: monospace; font-size: 10px;"
        "letter-spacing: 2px; background: transparent;"
    )
    return lbl


def mono_font(size: int = 10) -> QFont:
    """Return a real fixed-pitch (monospace) font.

    Unlike the CSS ``font-family: monospace`` generic family (which Qt does not
    reliably map to a fixed-pitch font in stylesheets), this sets the Monospace
    style hint so Qt always substitutes a genuine monospace font, matching the
    classic interface. Set it on a widget with ``setFont`` and make sure the
    widget's stylesheet does not override ``font-family``.

    :param size: Font size in pixels.
    """
    f = QFont("monospace")
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setFixedPitch(True)
    f.setPixelSize(size)
    return f


def section_title(text: str, icon_name: str = "folder") -> QWidget:
    row = QWidget()
    row.setStyleSheet("background: transparent;")
    hl = QHBoxLayout(row)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(9)
    icon = QLabel()
    icon.setPixmap(lucide.pixmap(icon_name, 16, PURPLE))
    icon.setFixedWidth(20)
    icon.setStyleSheet("background: transparent;")
    hl.addWidget(icon)
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {TEXT}; font-family: 'Brut Grotesque'; font-weight: 700;"
        " font-size: 15px; background: transparent;"
    )
    hl.addWidget(lbl)
    hl.addStretch()
    return row


def panel_inner() -> QWidget:
    """Scroll-area content root — grows vertically with the viewport; use one
    trailing ``addStretch(1)`` on the root layout so spare height stays below
    all controls (never between them)."""
    inner = QWidget()
    inner.setObjectName(PANEL_INNER)
    inner.setStyleSheet(f"background: {BG_PANEL};")
    inner.setMinimumWidth(SIDEBAR_CONTENT_MIN)
    inner.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    return inner


def param_row(label_text: str, value_text: str) -> QWidget:
    row = QFrame()
    row.setObjectName("ls-param-row")
    row.setStyleSheet(
        f"QFrame#ls-param-row {{ background: {BG_CARD};"
        f" border: 1px solid {BORDER}; border-radius: 5px; }}"
    )
    hl = QHBoxLayout(row)
    hl.setContentsMargins(12, 9, 12, 9)
    hl.setSpacing(12)
    key = QLabel(label_text)
    key.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;")
    hl.addWidget(key)
    hl.addStretch()
    val = QLabel(value_text)
    val.setStyleSheet(
        f"color: {TEXT}; font-family: monospace; font-size: 11px;"
        " background: transparent;"
    )
    val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    hl.addWidget(val)
    return row


def separator() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet("QFrame { background: rgba(255,255,255,0.08); }")
    line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return line


def hline() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"QFrame {{ background: {BORDER}; }}")
    line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return line


def vline() -> QFrame:
    line = QFrame()
    line.setFixedWidth(1)
    line.setStyleSheet(f"QFrame {{ background: {BORDER}; }}")
    line.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
    return line


# ── Resizable splitter with a thin 1px handle ─────────────────────────────────
_SPLIT_BG = QColor(10, 10, 10)              # ~BG_MAIN, near-black
_SPLIT_LINE = QColor(255, 255, 255, 28)     # matches the 1px border
_SPLIT_LINE_HOVER = QColor(212, 160, 255, 150)  # purple accent on hover


class _SplitHandle(QSplitterHandle):
    """A wide (grabbable) splitter handle that paints a 1px centered line."""

    def __init__(self, orientation, parent) -> None:
        super().__init__(orientation, parent)
        self._hover = False

    def enterEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        rect = self.rect()
        painter.fillRect(rect, _SPLIT_BG)
        color = _SPLIT_LINE_HOVER if self._hover else _SPLIT_LINE
        if self.orientation() == Qt.Orientation.Horizontal:
            x = (rect.width() - 1) // 2
            painter.fillRect(x, 0, 1, rect.height(), color)
        else:
            y = (rect.height() - 1) // 2
            painter.fillRect(0, y, rect.width(), 1, color)
        painter.end()


class LineSplitter(QSplitter):
    """
    QSplitter whose handles look like the design's 1px dividers but expose a
    wider grab zone for resizing. Children never collapse to zero.
    """

    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None) -> None:
        super().__init__(orientation, parent)
        self.setHandleWidth(7)
        self.setChildrenCollapsible(False)

    def createHandle(self) -> QSplitterHandle:  # noqa: N802 (Qt override)
        return _SplitHandle(self.orientation(), self)
