"""Sub-panel stack, sub-category tab bar, and the 3x3 stage positioning pad."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QEvent, QObject, QSize, Qt
from PyQt6.QtGui import QFocusEvent, QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from laserstudio.instruments.stage import StageInstrument, Vector
from laserstudio.widgets.keyboardbox import Direction, arrow_key_direction, direction_axis
from laserstudio.widgets.newui import lucide, theme

from ._helpers import _step_field
from ._styles import _DPAD_CELL, _DPAD_GAP, _DPAD_MIN_WIDTH, _DPAN_BTN, _SUB_BAR_SS, _Z_BTN


class _SubPanelStack(QStackedWidget):
    """Stack whose height follows the visible panel, not the tallest one."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:  # type: ignore[override]
        current = self.currentWidget()
        if current is not None:
            return current.sizeHint()
        return super().sizeHint()

    def minimumSizeHint(self) -> QSize:  # type: ignore[override]
        current = self.currentWidget()
        if current is not None:
            return current.minimumSizeHint()
        return super().minimumSizeHint()

    def setCurrentIndex(self, index: int) -> None:
        super().setCurrentIndex(index)
        self.updateGeometry()
        parent = self.parentWidget()
        if parent is not None:
            parent.updateGeometry()


class SubCategoryBar(QWidget):
    """2-column grid of sub-category tabs (Camera / Positioning / …)."""

    _COLS = 2

    def __init__(
        self,
        tabs: list[tuple[str, str, str]],
        on_select: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ls-sub-bar")
        self.setStyleSheet(_SUB_BAR_SS)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        for c in range(self._COLS):
            grid.setColumnStretch(c, 1)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for i, (key, label, icon_name) in enumerate(tabs):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("ls_key", key)
            btn.setProperty("ls_icon", icon_name)
            btn.setIcon(lucide.icon(icon_name, 14, theme.TAB_INACTIVE))
            btn.setIconSize(QSize(14, 14))
            btn.setToolTip(label)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _c=False, k=key: on_select(k))
            self._group.addButton(btn)
            grid.addWidget(btn, i // self._COLS, i % self._COLS)

    def select(self, key: str) -> None:
        for btn in self._group.buttons():
            active = btn.property("ls_key") == key
            btn.setChecked(active)
            icon = str(btn.property("ls_icon"))
            btn.setIcon(
                lucide.icon(icon, 14, theme.PURPLE if active else theme.TAB_INACTIVE)
            )


def _keyboard_toggle_button() -> QPushButton:
    """Checkable keyboard-control toggle button placed below a D-pad.

    Keyboard control is enabled/disabled *only* through this button (checked =
    enabled). It must not steal focus from the D-pad, which needs it to receive
    the arrow-key events while enabled.
    """
    btn = QPushButton("  Keyboard control")
    btn.setCheckable(True)
    btn.setIcon(lucide.icon("keyboard", 14, theme.TEXT_DIM))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setToolTip(
        "Enable keyboard control, then move with the arrow keys "
        "(Z with Page Up / Page Down). Shift ×10, Ctrl ×0.1."
    )
    btn.setStyleSheet(
        f"QPushButton {{ background: {theme.BG_CARD}; color: {theme.TEXT_DIM};"
        f" border: 1px solid {theme.BORDER}; border-radius: 5px; padding: 5px 10px;"
        " font-size: 11px; }"
        f" QPushButton:hover {{ border-color: {theme.PURPLE}; }}"
        f" QPushButton:checked {{ color: {theme.PURPLE};"
        f" border-color: {theme.PURPLE}; background: {theme.PURPLE_BG}; }}"
    )
    return btn


class DpadWidget(QWidget):
    """3×3 positioning pad wired to a stage instrument."""

    def __init__(
        self,
        stage: StageInstrument,
        *,
        include_home: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._stage = stage
        self._include_home = include_home
        self._num_axis = stage.num_axis
        self._displacement_xy = 100.0
        self._displacement_z = 10.0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        pad = QWidget()
        pad.setStyleSheet("background: transparent;")
        # +2 keeps a 1px margin around the grid so the outermost buttons'
        # borders are never clipped at the pad's edge.
        pad.setFixedWidth(_DPAD_MIN_WIDTH + 2)
        grid = QGridLayout(pad)
        grid.setContentsMargins(1, 1, 1, 1)
        grid.setHorizontalSpacing(_DPAD_GAP)
        grid.setVerticalSpacing(_DPAD_GAP)

        btn_policy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn_size = QSize(_DPAD_CELL, 40)

        if self._num_axis > 1:
            grid.addWidget(self._arrow_btn("arrow-up", Direction.up), 0, 1)
        if self._num_axis > 0:
            grid.addWidget(self._arrow_btn("arrow-left", Direction.left), 1, 0)
            if self._include_home:
                grid.addWidget(self._home_btn(), 1, 1)
            else:
                spacer = QWidget()
                spacer.setFixedSize(btn_size)
                spacer.setStyleSheet("background: transparent;")
                grid.addWidget(spacer, 1, 1)
            grid.addWidget(self._arrow_btn("arrow-right", Direction.right), 1, 2)
        if self._num_axis > 1:
            grid.addWidget(self._arrow_btn("arrow-down", Direction.down), 2, 1)
        if self._num_axis > 2:
            grid.addWidget(self._z_btn("Z+", Direction.zup), 0, 2)
            grid.addWidget(self._z_btn("Z−", Direction.zdown), 2, 2)

        for i in range(grid.count()):
            item = grid.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, QPushButton):
                widget.setFixedSize(btn_size)
                widget.setSizePolicy(btn_policy)

        self._pad = pad

        pad_wrap = QHBoxLayout()
        pad_wrap.setContentsMargins(0, 0, 0, 0)
        pad_wrap.addStretch()
        pad_wrap.addWidget(pad)
        pad_wrap.addStretch()
        root.addLayout(pad_wrap)

        # Keyboard control: a separate toggle below the pad. It is the only way to
        # enable keyboard control (clicking the pad itself must not enable it), so
        # the pad only accepts focus programmatically (TabFocus, not ClickFocus).
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._kbd_btn = _keyboard_toggle_button()
        self._kbd_btn.toggled.connect(self._on_keyboard_toggled)
        root.addWidget(self._kbd_btn)

        if self._num_axis > 0:
            xy_field, self._xy_spin = _step_field(
                "STEP X/Y", self._displacement_xy, 5.0, self._on_xy_step_changed
            )
            root.addWidget(xy_field)
        if self._num_axis > 2:
            z_field, self._z_spin = _step_field(
                "STEP Z", self._displacement_z, 10.0, self._on_z_step_changed
            )
            root.addWidget(z_field)

    def _on_xy_step_changed(self, value: float) -> None:
        self._displacement_xy = value

    def _on_z_step_changed(self, value: float) -> None:
        self._displacement_z = value

    def _arrow_btn(self, icon: str, direction: Direction) -> QPushButton:
        btn = QPushButton()
        btn.setIcon(lucide.icon(icon, 16, theme.TEXT))
        btn.setStyleSheet(_DPAN_BTN)
        # Do not steal focus from the pad, so keyboard control stays enabled.
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.clicked.connect(lambda: self._move(direction))
        return btn

    def _z_btn(self, label: str, direction: Direction) -> QPushButton:
        btn = QPushButton(label)
        btn.setStyleSheet(_Z_BTN)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.clicked.connect(lambda: self._move(direction))
        return btn

    def _home_btn(self) -> QPushButton:
        btn = QPushButton()
        btn.setIcon(lucide.icon("home", 16, theme.TEXT_DIM))
        btn.setStyleSheet(_DPAN_BTN)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setEnabled(self._num_axis > 0)
        btn.clicked.connect(self._go_origin)
        return btn

    def _go_origin(self) -> None:
        self._stage.move_to(Vector(*([0.0] * self._num_axis)), wait=False)

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

        displacement = self._displacement_z if axe == 2 else self._displacement_xy
        if direction in (Direction.down, Direction.left, Direction.zdown):
            displacement *= -1
        displacement *= factor

        position = self._stage.position
        position[axe] += displacement
        self._stage.move_to(position, wait=False)

    # ── Keyboard control ────────────────────────────────────────────────────
    def _on_keyboard_toggled(self, checked: bool) -> None:
        if checked:
            self.setFocus(Qt.FocusReason.OtherFocusReason)
        elif self.hasFocus():
            self.clearFocus()
        else:
            self.setFocus(Qt.FocusReason.MouseFocusReason)

    def _reposition_keyboard_button(self) -> None:
        btn, pad = self._kbd_btn, self._pad
        btn.move(pad.width() - btn.width(), pad.height() - btn.height())
        btn.raise_()

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if a0 is self._pad and a1 is not None and a1.type() == QEvent.Type.Resize:
            self._reposition_keyboard_button()
        return super().eventFilter(a0, a1)

    def _set_keyboard_active(self, active: bool) -> None:
        color = theme.PURPLE if active else theme.TEXT_DIM
        self._kbd_btn.setIcon(lucide.icon("keyboard", 14, color))
        self._pad.setStyleSheet(
            "background: transparent;"
            + (
                f" border: 1px solid {theme.PURPLE}; border-radius: 6px;"
                if active
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
