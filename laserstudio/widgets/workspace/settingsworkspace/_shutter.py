"""Shutter heading (with live status) + Open / Closed toggles."""

from __future__ import annotations

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from laserstudio.instruments.shutter import ShutterInstrument
from laserstudio.widgets.newui import lucide, theme

from ._styles import _FIELD_CONTROL_H, _SHUTTER_BTN_SS, _SHUTTER_CLOSED, _SHUTTER_OPEN


class _ShutterSection(QWidget):
    """Shutter heading (with live status) + Open / Closed toggles."""

    def __init__(
        self, shutter: ShutterInstrument, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._shutter = shutter

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        header = QWidget()
        header.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(9)
        icon = QLabel()
        icon.setPixmap(lucide.pixmap("aperture", 16, theme.PURPLE))
        icon.setFixedWidth(20)
        icon.setStyleSheet("background: transparent;")
        header_layout.addWidget(icon)
        title = QLabel("Shutter")
        title.setStyleSheet(
            f"color: {theme.TEXT}; font-family: 'Brut Grotesque'; font-weight: 700;"
            " font-size: 15px; background: transparent;"
        )
        header_layout.addWidget(title)
        header_layout.addStretch()
        self._status_lbl = QLabel()
        self._status_lbl.setStyleSheet(
            "font-family: monospace; font-size: 10px; letter-spacing: 1px;"
            " background: transparent;"
        )
        header_layout.addWidget(self._status_lbl)
        root.addWidget(header)

        row = QWidget()
        row.setObjectName("ls-shutter-row")
        row.setStyleSheet(_SHUTTER_BTN_SS)
        btn_layout = QHBoxLayout(row)
        btn_layout.setContentsMargins(3, 3, 3, 3)
        btn_layout.setSpacing(6)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        btn_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._open_btn = QPushButton("Open")
        self._open_btn.setObjectName("ls-shutter-open")
        self._open_btn.setCheckable(True)
        self._open_btn.setIconSize(QSize(13, 13))
        self._open_btn.setFixedHeight(_FIELD_CONTROL_H)
        self._open_btn.setSizePolicy(btn_policy)

        self._closed_btn = QPushButton("Closed")
        self._closed_btn.setObjectName("ls-shutter-closed")
        self._closed_btn.setCheckable(True)
        self._closed_btn.setIconSize(QSize(13, 13))
        self._closed_btn.setFixedHeight(_FIELD_CONTROL_H)
        self._closed_btn.setSizePolicy(btn_policy)

        self._group.addButton(self._open_btn)
        self._group.addButton(self._closed_btn)
        self._open_btn.clicked.connect(lambda: self._apply(True))
        self._closed_btn.clicked.connect(lambda: self._apply(False))
        btn_layout.addWidget(self._open_btn)
        btn_layout.addWidget(self._closed_btn)
        root.addWidget(row)

        self._sync_ui()

    def _apply(self, open_state: bool) -> None:
        if self._shutter.open != open_state:
            self._shutter.open = open_state
        self._sync_ui()

    def _sync_ui(self) -> None:
        open_state = self._shutter.open
        for btn, checked in (
            (self._open_btn, open_state),
            (self._closed_btn, not open_state),
        ):
            btn.blockSignals(True)
            btn.setChecked(checked)
            btn.blockSignals(False)
        # Icons follow the active state color (green open / orange closed),
        # muted otherwise — matching the button text color like the design.
        self._open_btn.setIcon(
            lucide.icon(
                "circle-dot",
                13,
                _SHUTTER_OPEN if open_state else theme.TEXT_MUTED,
            )
        )
        self._closed_btn.setIcon(
            lucide.icon(
                "circle",
                13,
                _SHUTTER_CLOSED if not open_state else theme.TEXT_MUTED,
            )
        )
        if open_state:
            self._status_lbl.setText("OPEN")
            self._status_lbl.setStyleSheet(
                f"color: {_SHUTTER_OPEN}; font-family: monospace; font-size: 10px;"
                " letter-spacing: 1px; background: transparent;"
            )
        else:
            self._status_lbl.setText("CLOSED")
            self._status_lbl.setStyleSheet(
                f"color: {_SHUTTER_CLOSED}; font-family: monospace; font-size: 10px;"
                " letter-spacing: 1px; background: transparent;"
            )
