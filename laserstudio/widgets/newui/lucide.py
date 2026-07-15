"""
Lucide icon helpers for PyQt6.

Renders Lucide-compatible SVG paths into QIcon/QPixmap objects
with configurable size and stroke colour. All icons use:
  viewBox="0 0 24 24", fill="none", stroke-linecap="round",
  stroke-linejoin="round", stroke-width="1.6"  (Lucide defaults).
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

# ---------------------------------------------------------------------------
# SVG path fragments — one entry per icon name.
# The full <svg> wrapper is added by _render().
# ---------------------------------------------------------------------------
_PATHS: dict[str, str] = {
    # ── File / folder ────────────────────────────────────────────────────────
    "folder": (
        '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9'
        "L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z\"/>"
    ),
    "folder-open": (
        '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5'
        "l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5c0-1.1.9-2 2-2h3.93"
        'a2 2 0 0 1 1.66.9l.82 1.2a2 2 0 0 0 1.66.9H18a2 2 0 0 1 2 2v2"/>'
    ),
    "file-cog": (
        '<path d="M4 22h14a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v3"/>'
        '<path d="M14 2v4a2 2 0 0 0 2 2h4"/>'
        '<circle cx="6" cy="14" r="3"/>'
        '<path d="M6 10v1"/><path d="M6 17v1"/>'
        '<path d="M10 14H9"/><path d="M3 14H2"/>'
        '<path d="m8.5 11.5-.5.5"/><path d="m4 16.5-.5.5"/>'
        '<path d="m9.5 16.5.5.5"/><path d="m3.5 11.5-.5.5"/>'
    ),
    "save": (
        '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19'
        'a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/>'
        '<path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"/>'
        '<path d="M7 3v4a1 1 0 0 0 1 1h7"/>'
    ),
    # ── Navigation / links ───────────────────────────────────────────────────
    "external-link": (
        '<path d="M15 3h6v6"/>'
        '<path d="M10 14 21 3"/>'
        '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
    ),
    # ── Instruments ──────────────────────────────────────────────────────────
    "camera": (
        '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16'
        'a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/>'
        '<circle cx="12" cy="13" r="3"/>'
    ),
    "zap": (
        '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46'
        "l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2"
        'a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>'
    ),
    "lightbulb": (
        '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5'
        'A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/>'
        '<path d="M9 18h6"/>'
        '<path d="M10 22h4"/>'
    ),
    "crosshair": (
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="22" y1="12" x2="18" y2="12"/>'
        '<line x1="6" y1="12" x2="2" y2="12"/>'
        '<line x1="12" y1="6" x2="12" y2="2"/>'
        '<line x1="12" y1="22" x2="12" y2="18"/>'
    ),
    "move": (
        '<path d="M5 9 2 12l3 3"/>'
        '<path d="M2 12h20"/>'
        '<path d="m19 9 3 3-3 3"/>'
        '<path d="m9 5 3-3 3 3"/>'
        '<path d="M12 2v20"/>'
        '<path d="m9 19 3 3 3-3"/>'
    ),
    "scan-eye": (
        '<path d="M3 7V5a2 2 0 0 1 2-2h2"/>'
        '<path d="M17 3h2a2 2 0 0 1 2 2v2"/>'
        '<path d="M21 17v2a2 2 0 0 1-2 2h-2"/>'
        '<path d="M7 21H5a2 2 0 0 1-2-2v-2"/>'
        '<circle cx="12" cy="12" r="1"/>'
        '<path d="M18.944 12.33a1 1 0 0 0 0-.66 7.5 7.5 0 0 0-13.888 0'
        ' 1 1 0 0 0 0 .66 7.5 7.5 0 0 0 13.888 0"/>'
    ),
    "aperture": (
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="m14.31 8 5.74 9.94"/>'
        '<path d="M9.69 8h11.48"/>'
        '<path d="m7.38 12 5.74-9.94"/>'
        '<path d="M9.69 16 3.95 6.06"/>'
        '<path d="M14.31 16H2.83"/>'
        '<path d="m16.62 12-5.74 9.94"/>'
    ),
    "scan": (
        '<path d="M3 7V5a2 2 0 0 1 2-2h2"/>'
        '<path d="M17 3h2a2 2 0 0 1 2 2v2"/>'
        '<path d="M21 17v2a2 2 0 0 1-2 2h-2"/>'
        '<path d="M7 21H5a2 2 0 0 1-2-2v-2"/>'
    ),
    "activity": (
        '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0'
        "L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2\"/>"
    ),
    "sliders-horizontal": (
        '<line x1="21" x2="14" y1="4" y2="4"/>'
        '<line x1="10" x2="3" y1="4" y2="4"/>'
        '<line x1="21" x2="12" y1="12" y2="12"/>'
        '<line x1="8" x2="3" y1="12" y2="12"/>'
        '<line x1="21" x2="16" y1="20" y2="20"/>'
        '<line x1="12" x2="3" y1="20" y2="20"/>'
        '<line x1="14" x2="14" y1="2" y2="6"/>'
        '<line x1="8" x2="8" y1="10" y2="14"/>'
        '<line x1="16" x2="16" y1="18" y2="22"/>'
    ),
    # ── Positioning / navigation ───────────────────────────────────────────────
    "move-3d": (
        '<path d="M5 3v16h16"/>'
        '<path d="m5 19 6-6"/>'
        '<path d="m2 6 3-3 3 3"/>'
        '<path d="m18 16 3 3-3 3"/>'
    ),
    "home": (
        '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
        '<polyline points="9 22 9 12 15 12 15 22"/>'
    ),
    "arrow-up": (
        '<path d="m5 12 7-7 7 7"/>'
        '<path d="M12 19V5"/>'
    ),
    "arrow-down": (
        '<path d="m5 12 7 7 7-7"/>'
        '<path d="M12 5v14"/>'
    ),
    "arrow-left": (
        '<path d="m12 19-7-7 7-7"/>'
        '<path d="M19 12H5"/>'
    ),
    "arrow-right": (
        '<path d="m12 5 7 7-7 7"/>'
        '<path d="M5 12h14"/>'
    ),
    "image": (
        '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/>'
        '<circle cx="9" cy="9" r="2"/>'
        '<path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>'
    ),
    "trash-2": (
        '<path d="M3 6h18"/>'
        '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
        '<line x1="10" x2="10" y1="11" y2="17"/>'
        '<line x1="14" x2="14" y1="11" y2="17"/>'
    ),
    "chevron-down": ('<path d="m6 9 6 6 6-6"/>'),
    "x": (
        '<path d="M18 6 6 18"/>'
        '<path d="m6 6 12 12"/>'
    ),
    "check": (
        '<path d="M20 6 9 17l-5-5"/>'
    ),
    "locate-fixed": (
        '<line x1="2" x2="5" y1="12" y2="12"/>'
        '<line x1="19" x2="22" y1="12" y2="12"/>'
        '<line x1="12" x2="12" y1="2" y2="5"/>'
        '<line x1="12" x2="12" y1="19" y2="22"/>'
        '<circle cx="12" cy="12" r="7"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    "spline": (
        '<path d="M3 17c3-6 6-6 9 0s6 6 9 0"/>'
        '<path d="M3 7c3-6 6-6 9 0s6 6 9 0"/>'
    ),
    "grid-3x3": (
        '<rect width="18" height="18" x="3" y="3" rx="2"/>'
        '<path d="M3 9h18"/>'
        '<path d="M3 15h18"/>'
        '<path d="M9 3v18"/>'
        '<path d="M15 3v18"/>'
    ),
    "circle": ('<circle cx="12" cy="12" r="10"/>'),
    "circle-dot": (
        '<circle cx="12" cy="12" r="10"/>'
        '<circle cx="12" cy="12" r="1"/>'
    ),
}


def _device_pixel_ratio() -> float:
    """Device pixel ratio of the primary screen (2.0 on Retina), else 1.0."""
    app = QGuiApplication.instance()
    if app is not None:
        screen = app.primaryScreen()
        if screen is not None:
            return screen.devicePixelRatio()
    return 1.0


def _render(paths: str, size: int, color: str) -> QPixmap:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg"'
        f' width="{size}" height="{size}" viewBox="0 0 24 24"'
        f' fill="none" stroke="{color}"'
        f' stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
        f"{paths}</svg>"
    )
    renderer = QSvgRenderer(svg.encode())
    # Render at the physical pixel resolution so the icon stays crisp on HiDPI
    # (Retina) displays, then tag the pixmap with the ratio so Qt draws it at
    # the intended logical size.
    dpr = _device_pixel_ratio()
    dim = max(1, round(size * dpr))
    pixmap = QPixmap(dim, dim)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def icon(name: str, size: int = 15, color: str = "#A3A3A3") -> QIcon:
    """Return a QIcon for the named Lucide icon at the given size and stroke colour."""
    paths = _PATHS.get(name)
    if paths is None:
        # Fallback: simple X mark so missing icons are visible in dev
        paths = '<line x1="4" y1="4" x2="20" y2="20"/><line x1="20" y1="4" x2="4" y2="20"/>'
    return QIcon(_render(paths, size, color))


def pixmap(name: str, size: int = 15, color: str = "#A3A3A3") -> QPixmap:
    """Return a QPixmap for the named Lucide icon."""
    paths = _PATHS.get(name)
    if paths is None:
        paths = '<line x1="4" y1="4" x2="20" y2="20"/><line x1="20" y1="4" x2="4" y2="20"/>'
    return _render(paths, size, color)


# ── Ledger single "L" logo ────────────────────────────────────────────────────
# Filled mark (not a stroke icon), viewBox 0 0 147 128. Rendered aspect-correct.
_LEDGER_LOGO_PATH = (
    "M0 91.6548V128H55.293V119.94H8.05631V91.6548H0ZM138.944 91.6548V119.94"
    "H91.707V127.998H147V91.6548H138.944ZM55.3733 36.3452V91.6529H91.707V84.3842"
    "H63.4296V36.3452H55.3733ZM0 0V36.3452H8.05631V8.05844H55.293V0H0ZM91.707 0"
    "V8.05844H138.944V36.3452H147V0H91.707Z"
)


def _render_filled(svg: str, size: int) -> QPixmap:
    """Render a complete <svg> string HiDPI-aware, preserving aspect ratio."""
    renderer = QSvgRenderer(svg.encode())
    dpr = _device_pixel_ratio()
    dim = max(1, round(size * dpr))
    px = QPixmap(dim, dim)
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    default = renderer.defaultSize()
    if default.width() > 0 and default.height() > 0:
        scale = min(dim / default.width(), dim / default.height())
        w = default.width() * scale
        h = default.height() * scale
        renderer.render(painter, QRectF((dim - w) / 2, (dim - h) / 2, w, h))
    else:
        renderer.render(painter)
    painter.end()
    px.setDevicePixelRatio(dpr)
    return px


def ledger_pixmap(size: int = 16, color: str = "#D4A0FF") -> QPixmap:
    """Return the Ledger single-L logo as a QPixmap in the given fill colour."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 147 128">'
        f'<path d="{_LEDGER_LOGO_PATH}" fill="{color}"/></svg>'
    )
    return _render_filled(svg, size)


def ledger_icon(size: int = 16, color: str = "#D4A0FF") -> QIcon:
    """Return the Ledger single-L logo as a QIcon."""
    return QIcon(ledger_pixmap(size, color))


def svg_file_pixmap(path: str, size: int) -> QPixmap:
    """Render an on-disk SVG file HiDPI-aware, preserving aspect ratio."""
    renderer = QSvgRenderer(path)
    if not renderer.isValid():
        return QPixmap()
    dpr = _device_pixel_ratio()
    dim = max(1, round(size * dpr))
    px = QPixmap(dim, dim)
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    default = renderer.defaultSize()
    if default.width() > 0 and default.height() > 0:
        scale = min(dim / default.width(), dim / default.height())
        w = default.width() * scale
        h = default.height() * scale
        renderer.render(painter, QRectF((dim - w) / 2, (dim - h) / 2, w, h))
    else:
        renderer.render(painter)
    painter.end()
    px.setDevicePixelRatio(dpr)
    return px


def svg_file_icon(path: str, size: int) -> QIcon:
    """Return a QIcon rendered from an SVG file on disk."""
    return QIcon(svg_file_pixmap(path, size))


# ── Microscope objective icon ─────────────────────────────────────────────────
# A stroked microscope-objective silhouette (new-UI style) with a coloured
# magnification band, following the standard manufacturer objective colour code
# (Nikon/Olympus/Leica/Zeiss, "Table 3"):
#     1/2x none · 1-1.5x black · 2-2.5x brown · 4-5x red · 10x yellow
#     16-20x green · 25-32x turquoise · 40-50x light blue · 60-63x cobalt blue
#     100-250x white
# The four objectives physically present on the bench (5x, 10x, 20x, 50x) keep
# the *exact* ring colour sampled from the classic-UI icons (obj-{mag}x.png) so
# the on-screen band matches the real objective the user handles.
_OBJECTIVE_RING_COLORS: dict[float, str | None] = {
    0.5: None,          # no colour assigned
    1.0: "#000000",     # black
    1.25: "#000000",    # black
    1.5: "#000000",     # black
    2.0: "#8B5A2B",     # brown
    2.5: "#8B5A2B",     # brown
    4.0: "#FF0000",     # red
    5.0: "#FF0000",     # red         (bench objective — sampled from obj-5x.png)
    10.0: "#FFED00",    # yellow      (bench objective — sampled from obj-10x.png)
    16.0: "#14FF00",    # green
    20.0: "#14FF00",    # green       (bench objective — sampled from obj-20x.png)
    25.0: "#2FD4C4",    # turquoise
    32.0: "#2FD4C4",    # turquoise
    40.0: "#7CB9FF",    # light blue
    50.0: "#0066FF",    # light blue  (bench objective — sampled from obj-50x.png)
    60.0: "#0047AB",    # cobalt blue
    63.0: "#0047AB",    # cobalt blue
    100.0: "#F5F5F5",   # white
    150.0: "#F5F5F5",   # white
    250.0: "#F5F5F5",   # white
}

# Objective silhouette (pointing down), viewBox 0 0 24 24: narrow mount on top,
# a straight-walled barrel, then a taper to the front lens.
_OBJECTIVE_BODY = "M9 3H15V5.5H17V13L14.5 20H9.5L7 13V5.5H9Z"
_OBJECTIVE_BODY_FILL = "#2A2A2E"


def objective_ring_color(mag: float) -> str | None:
    """Standard magnification-ring colour for the objective, or None if the code
    assigns no colour. Bench objectives keep their exact sampled colour."""
    if mag in _OBJECTIVE_RING_COLORS:
        return _OBJECTIVE_RING_COLORS[mag]
    # Nearest known magnification, so unusual values still get a sensible band.
    nearest = min(_OBJECTIVE_RING_COLORS, key=lambda m: abs(m - mag))
    return _OBJECTIVE_RING_COLORS[nearest]


def objective_pixmap(
    mag: float, size: int = 18, color: str = "#A3A3A3"
) -> QPixmap:
    """Render a microscope-objective icon with the magnification colour band."""
    ring = objective_ring_color(mag)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">',
        f'<path d="{_OBJECTIVE_BODY}" fill="{_OBJECTIVE_BODY_FILL}"'
        ' stroke="none"/>',
    ]
    if ring is not None:
        # A hairline rim around the band keeps dark codes (black, brown, cobalt)
        # legible against the dark barrel while staying subtle on bright codes.
        parts.append(
            f'<rect x="7" y="8" width="10" height="3.2" fill="{ring}"'
            ' stroke="#FFFFFF" stroke-opacity="0.25" stroke-width="0.5"/>'
        )
    parts.append(
        f'<path d="{_OBJECTIVE_BODY}" fill="none" stroke="{color}"'
        ' stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    parts.append("</svg>")
    return _render_filled("".join(parts), size)


def objective_icon(mag: float, size: int = 18, color: str = "#A3A3A3") -> QIcon:
    """Return a QIcon for a microscope objective at the given magnification."""
    return QIcon(objective_pixmap(mag, size, color))
