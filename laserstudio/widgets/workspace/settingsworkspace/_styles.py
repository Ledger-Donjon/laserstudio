"""QSS style constants and layout dimensions shared by the settings panels."""

from __future__ import annotations

from pathlib import Path

from laserstudio.widgets.newui import theme

# Fixed tabs header + scrollable sub-panel content; see build_panel.
_DPAD_CELL = 44
_DPAD_GAP = 6
_DPAD_MIN_WIDTH = _DPAD_CELL * 3 + _DPAD_GAP * 2
_ICONS_DIR = Path(__file__).resolve().parents[3] / "icons"

# ── Styles ─────────────────────────────────────────────────────────────────────

_DPAN_BTN = f"""
QPushButton {{
    background: rgba(255,255,255,0.05);
    color: {theme.TEXT};
    border: 1px solid {theme.BORDER};
    border-radius: 5px;
    min-height: 40px;
    padding: 0;
}}
QPushButton:hover {{ background: rgba(255,255,255,0.09); }}
QPushButton:pressed {{ padding-top: 1px; }}
QPushButton:disabled {{
    color: {theme.TEXT_DIM};
    background: rgba(255,255,255,0.02);
    border-color: rgba(255,255,255,0.06);
}}
"""

_Z_BTN = f"""
QPushButton {{
    background: {theme.PURPLE_BG};
    color: {theme.PURPLE};
    border: 1px solid {theme.PURPLE_BORDER};
    border-radius: 5px;
    font-family: monospace;
    font-size: 11px;
    min-height: 40px;
    padding: 0;
}}
QPushButton:hover {{ background: rgba(212,160,255,0.20); }}
QPushButton:pressed {{ padding-top: 1px; }}
"""

# Scoped under #ls-sub-bar so the global ledger QPushButton:checked (orange) does not win.
_SUB_BAR_SS = f"""
QWidget#ls-sub-bar QPushButton {{
    background-color: transparent;
    color: {theme.TAB_INACTIVE};
    border: 1px solid {theme.BORDER_SUBTLE};
    border-radius: 5px;
    font-family: "Brut Grotesque";
    font-size: 11px;
    font-weight: 700;
    text-align: left;
    padding: 6px 10px;
    min-height: 0;
}}
QWidget#ls-sub-bar QPushButton:hover {{
    color: {theme.TEXT};
    background-color: rgba(255,255,255,0.05);
}}
QWidget#ls-sub-bar QPushButton:checked {{
    background-color: {theme.PURPLE_BG};
    color: {theme.PURPLE};
    border: 1px solid {theme.PURPLE_BORDER};
}}
QWidget#ls-sub-bar QPushButton:checked:hover {{
    background-color: rgba(212,160,255,0.18);
    color: {theme.PURPLE};
    border-color: rgba(212,160,255,0.50);
}}
"""

_CLICK_MOVE_BTN = f"""
QPushButton#ls-click-move-btn {{
    background-color: rgba(255,255,255,0.05);
    color: {theme.TEXT};
    border: 1px solid {theme.BORDER};
    border-radius: 5px;
    font-family: "Brut Grotesque";
    font-size: 12px;
    padding: 6px 12px;
    text-align: left;
}}
QPushButton#ls-click-move-btn:hover {{
    background-color: rgba(255,255,255,0.09);
}}
QPushButton#ls-click-move-btn:checked {{
    background-color: {theme.PURPLE_BG};
    color: {theme.PURPLE};
    border: 1px solid {theme.PURPLE_BORDER};
}}
"""

# Shutter Open/Closed — separate toggles (design), not a single pill.
_SHUTTER_OPEN = theme.GREEN
_SHUTTER_OPEN_BG = theme.GREEN_BG
_SHUTTER_OPEN_BORDER = "rgba(110,200,92,0.40)"
_SHUTTER_CLOSED = theme.ACCENT
_SHUTTER_CLOSED_BG = "rgba(255,83,0,0.12)"
_SHUTTER_CLOSED_BORDER = "rgba(255,83,0,0.40)"

# Laser ARM button — subtle accent when safe, filled accent when armed.
_LASER_ARM_SAFE_SS = f"""
QPushButton {{
    background: rgba(255,83,0,0.10);
    color: {theme.ACCENT};
    border: 1px solid rgba(255,83,0,0.50);
    border-radius: 5px;
    font-family: "Brut Grotesque";
    font-weight: 700;
    font-size: 12px;
    padding: 6px 14px;
    min-height: 0;
    max-height: {theme.BTN_MIN_H}px;
}}
QPushButton:hover {{ background: rgba(255,83,0,0.18); }}
"""
_LASER_ARM_ARMED_SS = f"""
QPushButton {{
    background: {theme.ACCENT};
    color: #0A0A0A;
    border: 1px solid {theme.ACCENT};
    border-radius: 5px;
    font-family: "Brut Grotesque";
    font-weight: 700;
    font-size: 12px;
    padding: 6px 14px;
    min-height: 0;
    max-height: {theme.BTN_MIN_H}px;
}}
QPushButton:hover {{ background: #FF6A26; }}
"""

# Segmented control (design): a rounded container holding two borderless
# buttons that fill with a tint when active.
_SHUTTER_BTN_SS = f"""
QWidget#ls-shutter-row {{
    background-color: {theme.BG_CARD};
    border: 1px solid {theme.BORDER};
    border-radius: 6px;
}}
QWidget#ls-shutter-row QPushButton {{
    background-color: transparent;
    color: {theme.TEXT_MUTED};
    border: none;
    border-radius: 4px;
    font-family: "Brut Grotesque";
    font-weight: 700;
    font-size: 11px;
    padding: 6px 12px;
    min-height: 0;
    max-height: {theme.CONTROL_MIN_H}px;
}}
QWidget#ls-shutter-row QPushButton:hover {{
    background-color: rgba(255,255,255,0.05);
    color: {theme.TEXT};
}}
QWidget#ls-shutter-row QPushButton#ls-shutter-open:checked {{
    background-color: {_SHUTTER_OPEN_BG};
    color: {_SHUTTER_OPEN};
}}
QWidget#ls-shutter-row QPushButton#ls-shutter-closed:checked {{
    background-color: {_SHUTTER_CLOSED_BG};
    color: {_SHUTTER_CLOSED};
}}
"""

_TRASH_BTN_SS = f"""
QPushButton#ls-ref-trash {{
    background: rgba(255,255,255,0.05);
    border: 1px solid {theme.BORDER};
    border-radius: 5px;
    padding: 0;
}}
QPushButton#ls-ref-trash:hover {{
    color: #F04F52;
    border-color: rgba(240,79,82,0.4);
    background: rgba(240,79,82,0.08);
}}
QPushButton#ls-ref-trash:disabled {{
    color: {theme.TEXT_DIM};
    border-color: rgba(255,255,255,0.06);
    background: rgba(255,255,255,0.02);
}}
"""

_DIST_SET_BTN = f"""
QPushButton#ls-dist-set {{
    background: {theme.PURPLE_BG};
    color: {theme.PURPLE};
    border: 1px solid {theme.PURPLE_BORDER};
    border-radius: 5px;
    font-family: "Brut Grotesque";
    font-size: 11px;
    padding: 0 12px;
    min-height: 0;
    max-height: {theme.BTN_MIN_H}px;
}}
QPushButton#ls-dist-set:hover {{
    background: rgba(212,160,255,0.20);
}}
QPushButton#ls-dist-set:disabled {{
    color: {theme.TEXT_DIM};
    background: rgba(255,255,255,0.02);
    border-color: rgba(255,255,255,0.06);
}}
"""

PANEL_SPACING = 12
_SLIDER_ROW_H = 38

_FIELD_CONTROL_H = theme.CONTROL_MIN_H

_MONO_DIM = (
    f"color: {theme.TEXT_DIM}; font-family: monospace; font-size: 10px;"
    " background: transparent;"
)
_MONO_MUTED = (
    f"color: {theme.TEXT_MUTED}; font-family: monospace; font-size: 10px;"
    " background: transparent;"
)

_JOYSTICK_CAPSULE = f"""
QPushButton#ls-joy-capsule {{
    background-color: rgba(255,255,255,0.05);
    color: {theme.TEXT_MUTED};
    border: 1px solid {theme.BORDER};
    border-radius: 12px;
    font-family: "Brut Grotesque";
    font-weight: 700;
    font-size: 11px;
    padding: 4px 0;
    min-height: 26px;
}}
QPushButton#ls-joy-capsule:hover {{
    background-color: rgba(255,255,255,0.09);
}}
QPushButton#ls-joy-capsule:checked {{
    background-color: {theme.PURPLE_BG};
    color: {theme.PURPLE};
    border: 1px solid {theme.PURPLE_BORDER};
}}
"""
