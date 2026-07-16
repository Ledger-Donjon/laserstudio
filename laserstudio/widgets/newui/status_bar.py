"""Bottom status bar for the redesigned Laser Studio window."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from . import theme

_MONO = (
    f"color: {theme.TEXT_MUTED}; font-family: monospace; font-size: 10px;"
    " background: transparent;"
)


class StatusBar(QWidget):
    """Persistent 30 px status strip below the main content area."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ls-statusbar")
        self.setFixedHeight(30)
        self.setStyleSheet(
            f"QWidget#ls-statusbar {{ background: {theme.BG_PANEL};"
            f" border-top: 1px solid {theme.BORDER}; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(18)

        self._workspace = QLabel("CONFIG")
        self._workspace.setStyleSheet(
            f"color: {theme.PURPLE}; font-family: monospace; font-size: 10px;"
            " background: transparent;"
        )
        layout.addWidget(self._workspace)

        self._position = QLabel("X —  Y —  Z —")
        self._position.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; background: transparent;"
        )
        self._position.setFont(theme.mono_font(10))
        layout.addWidget(self._position)

        self._laser = QLabel("LASER SAFE")
        self._laser.setStyleSheet(
            f"color: {theme.GREEN}; font-family: monospace; font-size: 10px;"
            " background: transparent;"
        )
        layout.addWidget(self._laser)

        layout.addStretch()

        self._objective = QLabel("OBJ —")
        self._objective.setStyleSheet(_MONO)
        layout.addWidget(self._objective)

        self._connected = QLabel("● CONNECTED")
        self._connected.setStyleSheet(
            f"color: {theme.GREEN}; font-family: monospace; font-size: 10px;"
            " background: transparent;"
        )
        layout.addWidget(self._connected)

    def set_workspace(self, name: str) -> None:
        self._workspace.setText(name.upper())

    def set_position(self, coords: list[float] | tuple[float, ...]) -> None:
        parts: list[str] = []
        labels = ("X", "Y", "Z")
        for i, val in enumerate(coords[:3]):
            parts.append(f"{labels[i]} {val:+.1f}")
        while len(parts) < 3:
            parts.append(f"{labels[len(parts)]} —")
        self._position.setText("  ".join(parts))

    def set_laser_armed(self, armed: bool) -> None:
        if armed:
            self._laser.setText("LASER ARMED")
            self._laser.setStyleSheet(
                f"color: {theme.ACCENT}; font-family: monospace; font-size: 10px;"
                " background: transparent;"
            )
        else:
            self._laser.setText("LASER SAFE")
            self._laser.setStyleSheet(
                f"color: {theme.GREEN}; font-family: monospace; font-size: 10px;"
                " background: transparent;"
            )

    def set_objective(self, magnification: str | None) -> None:
        self._objective.setText(f"OBJ {magnification}" if magnification else "OBJ —")

    def set_connected(self, connected: bool) -> None:
        if connected:
            self._connected.setText("● CONNECTED")
            self._connected.setStyleSheet(
                f"color: {theme.GREEN}; font-family: monospace; font-size: 10px;"
                " background: transparent;"
            )
        else:
            self._connected.setText("○ OFFLINE")
            self._connected.setStyleSheet(
                f"color: {theme.TEXT_DIM}; font-family: monospace; font-size: 10px;"
                " background: transparent;"
            )
