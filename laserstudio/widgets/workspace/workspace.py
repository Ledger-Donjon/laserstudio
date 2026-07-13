"""
Base class for Laser Studio workspaces.

A :class:`Workspace` owns the widgets for one tab of the redesigned window:
a left-column *panel* and, optionally, a right-side *content* widget. When a
workspace returns ``None`` from :meth:`Workspace.build_content`, the main window
shows the shared spatial viewer instead.

Concrete workspaces live in their own modules next to this one
(``configworkspace.py``, ``settingsworkspace.py``, …).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from ..newui import theme


class Workspace:
    """
    Base class for a Laser Studio workspace tab.

    Subclasses set :attr:`label` (tab text) and :attr:`icon` (Lucide icon name),
    and may override :meth:`build_panel` (left column) and
    :meth:`build_content` (right side). The default panel is a
    "not yet implemented" placeholder and the default content is ``None``
    (meaning: use the shared viewer).
    """

    label: str = ""
    icon: str = ""

    def build_panel(self) -> QWidget:
        """Return the left-column panel widget for this workspace."""
        return placeholder_panel(self.label)

    def build_content(self) -> QWidget | None:
        """Return the right-side content, or ``None`` to use the viewer."""
        return None


def placeholder_panel(label: str) -> QWidget:
    """A simple 'not yet implemented' left panel, used by unfinished workspaces."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet(
        f"QScrollArea {{ border: none; background: {theme.BG_PANEL}; }}"
    )
    inner = QWidget()
    inner.setStyleSheet(f"background: {theme.BG_PANEL};")
    layout = QVBoxLayout(inner)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(16)
    layout.addWidget(theme.eyebrow(f"WORKSPACE · {label.upper()}"))
    note = QLabel("(not yet implemented)")
    note.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px;")
    note.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(note)
    layout.addStretch()
    scroll.setWidget(inner)
    return scroll
