"""New-UI styled stage jog pad used by the camera wizard pages.

Layout requested for the wizard (no Home button, the down arrow takes its place
in the centre, and Z+/Z- sit in a fourth column):

    [↑]            [Z+]
    [←] [↓] [→]    [Z−]

plus a "Keyboard control" toggle (arrow keys move the stage only while enabled)
and shared STEP X/Y and STEP Z fields.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFocusEvent, QKeyEvent
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QDoubleSpinBox,
    QLabel,
    QSizePolicy,
    QApplication,
)

from ..keyboardbox import Direction, arrow_key_direction, direction_axis
from ..newui import lucide, theme
from ...instruments.instruments import StageInstrument

_CELL = 40
_GAP = 6

_DPAD_SS = f"""
QPushButton {{
    background: rgba(255,255,255,0.05);
    color: {theme.TEXT};
    border: 1px solid {theme.BORDER};
    border-radius: 6px;
}}
QPushButton:hover {{ background: rgba(255,255,255,0.09); border-color: {theme.BORDER_HOVER}; }}
"""

_Z_SS = f"""
QPushButton {{
    background: {theme.PURPLE_BG};
    color: {theme.PURPLE};
    border: 1px solid {theme.PURPLE_BORDER};
    border-radius: 6px;
    font-family: monospace;
    font-size: 11px;
}}
QPushButton:hover {{ background: rgba(212,160,255,0.20); }}
"""

_STEP_SS = (
    f"background: {theme.BG_CARD}; color: {theme.TEXT};"
    f" border: 1px solid {theme.BORDER}; border-radius: 5px;"
    " font-family: monospace; font-size: 11px; padding: 0 8px;"
)


class WizardJogPanel(QWidget):
    """New-UI styled jog pad to move the stage from within a wizard page."""

    def __init__(self, stage: StageInstrument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._stage = stage
        self._num_axis = stage.num_axis
        self.step_xy = 100.0
        self.step_z = 10.0
        # Self-contained dark card, so it stays readable whatever the wizard
        # style is (the classic UI wizard has a light background).
        self.setObjectName("ls-wizard-jog")
        self.setStyleSheet(
            f"QWidget#ls-wizard-jog {{ background: {theme.BG_PANEL};"
            f" border: 1px solid {theme.BORDER}; border-radius: 8px; }}"
        )
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # ── D-pad grid ────────────────────────────────────────────────────────
        self._pad = QWidget()
        self._pad.setStyleSheet("background: transparent;")
        grid = QGridLayout(self._pad)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(_GAP)
        grid.setVerticalSpacing(_GAP)

        if self._num_axis > 1:
            grid.addWidget(self._arrow_btn("arrow-up", Direction.up), 0, 1)
        if self._num_axis > 0:
            grid.addWidget(self._arrow_btn("arrow-left", Direction.left), 1, 0)
        if self._num_axis > 1:
            # Down arrow takes the place of the (removed) Home button.
            grid.addWidget(self._arrow_btn("arrow-down", Direction.down), 1, 1)
        if self._num_axis > 0:
            grid.addWidget(self._arrow_btn("arrow-right", Direction.right), 1, 2)
        if self._num_axis > 2:
            # Z+ / Z- in a fourth column, visually separated by a gap column.
            grid.setColumnMinimumWidth(3, _GAP * 2)
            grid.addWidget(self._z_btn("Z+", Direction.zup), 0, 4)
            grid.addWidget(self._z_btn("Z−", Direction.zdown), 1, 4)

        for i in range(grid.count()):
            item = grid.itemAt(i)
            w = item.widget() if item is not None else None
            if isinstance(w, QPushButton):
                w.setFixedSize(QSize(_CELL, _CELL))
                w.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        root.addWidget(self._pad, alignment=Qt.AlignmentFlag.AlignHCenter)

        # ── Keyboard control toggle ───────────────────────────────────────────
        # Arrow keys move the stage only while this is enabled. The pad accepts
        # focus programmatically only (not on click), so clicking a button never
        # silently enables keyboard control.
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._kbd_btn = QPushButton("  Keyboard control")
        self._kbd_btn.setCheckable(True)
        self._kbd_btn.setIcon(lucide.icon("keyboard", 13, theme.TEXT_DIM))
        self._kbd_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._kbd_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._kbd_btn.setToolTip(
            "Enable keyboard control, then move with the arrow keys "
            "(Z with Page Up / Page Down). Shift ×10, Ctrl ×0.1."
        )
        self._kbd_btn.setStyleSheet(
            f"QPushButton {{ background: {theme.BG_CARD}; color: {theme.TEXT_DIM};"
            f" border: 1px solid {theme.BORDER}; border-radius: 5px;"
            " padding: 5px 10px; font-size: 11px; }"
            f" QPushButton:hover {{ border-color: {theme.PURPLE}; }}"
            f" QPushButton:checked {{ color: {theme.PURPLE};"
            f" border-color: {theme.PURPLE}; background: {theme.PURPLE_BG}; }}"
        )
        self._kbd_btn.toggled.connect(self._on_keyboard_toggled)
        root.addWidget(self._kbd_btn)

        # ── STEP fields ───────────────────────────────────────────────────────
        self.step_xy_spin = self._step_field("STEP X/Y", self.step_xy)
        self.step_xy_spin.valueChanged.connect(
            lambda v: setattr(self, "step_xy", float(v))
        )
        root.addLayout(self._step_row("STEP X/Y", self.step_xy_spin))
        if self._num_axis > 2:
            self.step_z_spin: QDoubleSpinBox | None = self._step_field(
                "STEP Z", self.step_z
            )
            self.step_z_spin.valueChanged.connect(
                lambda v: setattr(self, "step_z", float(v))
            )
            root.addLayout(self._step_row("STEP Z", self.step_z_spin))
        else:
            self.step_z_spin = None

    # ── Builders ──────────────────────────────────────────────────────────────
    def _arrow_btn(self, icon: str, direction: Direction) -> QPushButton:
        btn = QPushButton()
        btn.setIcon(lucide.icon(icon, 16, theme.TEXT))
        btn.setStyleSheet(_DPAD_SS)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.clicked.connect(lambda: self._move(direction))
        return btn

    def _z_btn(self, label: str, direction: Direction) -> QPushButton:
        btn = QPushButton(label)
        btn.setStyleSheet(_Z_SS)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.clicked.connect(lambda: self._move(direction))
        return btn

    def _step_field(self, _label: str, value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.1, 1_000_000)
        spin.setDecimals(1)
        spin.setValue(value)
        spin.setSuffix("\xa0µm")
        spin.setFixedHeight(theme.BTN_MIN_H)
        spin.setStyleSheet(_STEP_SS)
        return spin

    def _step_row(self, label: str, spin: QDoubleSpinBox) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-family: monospace; font-size: 10px;"
            " background: transparent;"
        )
        row.addWidget(lbl)
        row.addWidget(spin, stretch=1)
        return row

    # ── Movement ──────────────────────────────────────────────────────────────
    def _move(self, direction: Direction) -> None:
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            factor = 10.0
        elif modifiers & Qt.KeyboardModifier.ControlModifier:
            factor = 0.1
        else:
            factor = 1.0

        axe = direction_axis(direction)
        if axe >= self._num_axis:
            return
        displacement = (self.step_z if axe == 2 else self.step_xy) * factor
        if direction in (Direction.down, Direction.left, Direction.zdown):
            displacement = -displacement

        position = self._stage.position
        position[axe] += displacement
        self._stage.move_to(position, wait=False)

    # ── Keyboard control ──────────────────────────────────────────────────────
    def _on_keyboard_toggled(self, checked: bool) -> None:
        if checked:
            self.setFocus(Qt.FocusReason.OtherFocusReason)
        elif self.hasFocus():
            self.clearFocus()
        self._pad.setStyleSheet(
            "background: transparent;"
            + (
                f" border: 1px solid {theme.PURPLE}; border-radius: 6px;"
                if checked
                else ""
            )
        )

    def focusInEvent(self, a0: QFocusEvent | None) -> None:
        super().focusInEvent(a0)
        self._kbd_btn.setChecked(True)

    def focusOutEvent(self, a0: QFocusEvent | None) -> None:
        super().focusOutEvent(a0)
        self._kbd_btn.setChecked(False)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        direction = arrow_key_direction(a0.key()) if a0 is not None else None
        if direction is not None and direction_axis(direction) < self._num_axis:
            self._move(direction)
            if a0 is not None:
                a0.accept()
            return
        super().keyPressEvent(a0)
