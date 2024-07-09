from typing import Optional
from PyQt6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QGridLayout,
    QPushButton,
    QWidget,
    QApplication,
    QDoubleSpinBox,
)
from PyQt6.QtCore import Qt
from ..instruments.instruments import StageInstrument
from enum import Enum


class Direction(str, Enum):
    up = "U"
    right = "R"
    down = "D"
    left = "L"
    zup = "Z+"
    zdown = "Z-"


class KeyboardBox(QGroupBox):
    """
    Creates a control Box, associated to a Stage or StageSight.
    to permit to move the associated object by using
    buttons or the keyboard (when focused).
    Also contains Entries to configure the displacement steps
    for each press of button or keys.
    """

    def __init__(self, stage: StageInstrument, *__args):
        super().__init__(*__args)

        self.stage_instrument = stage
        self.stage = stage.stage
        num_axis = stage.stage.num_axis
        self.displacement_z = 10.0
        self.displacement_xy = 100.0

        vbox = QVBoxLayout()
        self.setLayout(vbox)

        grid = QGridLayout()
        if num_axis > 0:
            w = QPushButton(Direction.left)
            w.setFixedWidth(30)
            w.pressed.connect(lambda: self.move_stage(Direction.left))
            grid.addWidget(w, 2, 1, alignment=Qt.AlignmentFlag.AlignRight)
            w = QPushButton(Direction.right)
            w.setFixedWidth(30)
            w.pressed.connect(lambda: self.move_stage(Direction.right))
            grid.addWidget(w, 2, 3, alignment=Qt.AlignmentFlag.AlignLeft)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(3, 1)

            w = QDoubleSpinBox()
            w.setMinimum(0)
            w.setMaximum(1_000_000)
            w.setDecimals(1)
            w.setValue(self.displacement_z)
            w.valueChanged.connect(lambda v: self.__setattr__("displacement_xy", v))
            w.setSuffix(" µm")
            w.setSingleStep(5)
            grid.addWidget(w, 3, 1, 1, 3)

        if num_axis > 1:
            w = QPushButton(Direction.up)
            w.setFixedWidth(30)
            w.pressed.connect(lambda: self.move_stage(Direction.up))
            grid.addWidget(w, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
            w = QPushButton(Direction.down)
            w.setFixedWidth(30)
            w.pressed.connect(lambda: self.move_stage(Direction.down))
            grid.addWidget(w, 2, 2, alignment=Qt.AlignmentFlag.AlignCenter)
            grid.setColumnStretch(2, 1)
        if num_axis > 2:
            w = QPushButton(Direction.zup)
            w.setFixedWidth(30)
            w.pressed.connect(lambda: self.move_stage(Direction.zup))
            grid.addWidget(w, 1, 4)
            w = QPushButton(Direction.zdown)
            w.setFixedWidth(30)
            w.pressed.connect(lambda: self.move_stage(Direction.zdown))
            grid.addWidget(w, 2, 4)
            grid.setColumnStretch(4, 1)

            w = QDoubleSpinBox()
            w.setMinimum(0)
            w.setMaximum(1000000)
            w.setDecimals(1)
            w.setValue(self.displacement_z)
            w.valueChanged.connect(lambda v: self.__setattr__("displacement_z", v))
            w.setSuffix(" µm")
            w.setSingleStep(10)
            grid.addWidget(w, 3, 4)

        w = QWidget()
        w.setLayout(grid)
        vbox.addWidget(w)

        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        self._set_background_color()

    def move_stage(self, direction: Direction, coefficient: float = 1.0):
        # Give a factor if the keyboard SHIFT or ALT are pressed.
        modifiers = QApplication.keyboardModifiers()
        if Qt.KeyboardModifier.ShiftModifier in modifiers:
            move_factor = 10.0
        elif Qt.KeyboardModifier.ControlModifier in modifiers:
            move_factor = 0.1
        else:
            move_factor = 1.0

        if direction in [Direction.left, Direction.right]:
            axe = 0
        elif direction in [Direction.up, Direction.down]:
            axe = 1
        elif direction in [Direction.zup, Direction.zdown]:
            axe = 2
        else:
            print("Unexpected direction")
            return

        displacement = self.displacement_z if axe == 2 else self.displacement_xy
        if direction in [Direction.up, Direction.right, Direction.zup]:
            displacement *= 1
        elif direction in [Direction.down, Direction.left, Direction.zdown]:
            displacement *= -1

        displacement *= move_factor * abs(coefficient)

        position = self.stage_instrument.position
        position[axe] += displacement
        self.stage_instrument.move_to(position, wait=True)

    def _set_background_color(self, color: Optional[str] = None):
        """
        Convenience function to change the background color of the Box.

        :param color: The color to apply as background color.
        """
        self.setStyleSheet(
            "KeyboardBox { border-radius: 2px;"
            + (f"  background-color: {color};" if color else "")
            + "}"
        )

    def focusInEvent(self, a0) -> None:
        """
        Changes the background to gray to show the box has focused.
        """
        super().focusInEvent(a0)
        self._set_background_color(color="gray")

    def focusOutEvent(self, a0) -> None:
        """
        Removes the background color to show the box has focused out.
        """
        super().focusOutEvent(a0)
        self._set_background_color()

    def keyPressEvent(self, a0):
        """
        Detects a key press event and redispatch to the correct
        movement.
        """
        if a0 is None:
            return

        if a0.key() == Qt.Key.Key_Up:
            self.move_stage(direction=Direction.up)
        elif a0.key() == Qt.Key.Key_Down:
            self.move_stage(direction=Direction.down)
        elif a0.key() == Qt.Key.Key_Left:
            self.move_stage(direction=Direction.left)
        elif a0.key() == Qt.Key.Key_Right:
            self.move_stage(direction=Direction.right)
        elif a0.key() == Qt.Key.Key_PageUp:
            self.move_stage(direction=Direction.zup)
        elif a0.key() == Qt.Key.Key_PageDown:
            self.move_stage(direction=Direction.zdown)
        else:
            super().keyPressEvent(a0)
