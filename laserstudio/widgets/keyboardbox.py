from typing import Union, Optional
from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QGridLayout, QPushButton, QWidget
from PyQt6.QtCore import Qt
from ..instruments.instruments import StageInstrument
from ..widgets.stagesight import StageSight
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

    def __init__(self, stage: Union[StageSight, StageInstrument], *__args):
        super().__init__(*__args)

        if isinstance(stage, StageInstrument):
            self.stage_sight = None
            self.stage = stage.stage
            num_axis = stage.stage.num_axis
        else:
            self.stage_sight = stage
            self.stage = None
            num_axis = 2

        vbox = QVBoxLayout()
        self.setLayout(vbox)

        grid = QGridLayout()
        if num_axis > 0:
            w = QPushButton(Direction.left)
            w.pressed.connect(lambda: self.move_stage(Direction.left))
            grid.addWidget(w, 2, 1)
            w = QPushButton(Direction.right)
            w.pressed.connect(lambda: self.move_stage(Direction.right))
            grid.addWidget(w, 2, 3)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(3, 1)
        if num_axis > 1:
            w = QPushButton(Direction.up)
            w.pressed.connect(lambda: self.move_stage(Direction.up))
            grid.addWidget(w, 1, 2)
            w = QPushButton(Direction.down)
            w.pressed.connect(lambda: self.move_stage(Direction.down))
            grid.addWidget(w, 2, 2)
            grid.setColumnStretch(2, 1)
        if num_axis > 2:
            w = QPushButton(Direction.zup)
            w.pressed.connect(lambda: self.move_stage(Direction.zup))
            grid.addWidget(w, 1, 4)
            w = QPushButton(Direction.zdown)
            w.pressed.connect(lambda: self.move_stage(Direction.zdown))
            grid.addWidget(w, 2, 4)
            grid.setColumnStretch(4, 1)

        w = QWidget()
        w.setLayout(grid)
        vbox.addWidget(w)

        self.displacement_z = 1.0
        self.displacement_xy = 1.0

        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def move_stage(self, direction: Direction):
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

        if self.stage is not None:
            position = self.stage.position
            position[axe] += displacement
            self.stage.move_to(position)
        elif self.stage_sight is not None:
            position = self.stage_sight.pos()
            if axe == 0:
                position.setX(position.x() + displacement)
            elif axe == 1:
                position.setY(position.y() + displacement)
            self.stage_sight.move_to(position)

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

    def focusInEvent(self, event) -> None:
        """
        Changes the background to gray to show the box has focused.
        """
        super().focusInEvent(event)
        self._set_background_color(color="gray")

    def focusOutEvent(self, event) -> None:
        """
        Removes the background color to show the box has focused out.
        """
        super().focusOutEvent(event)
        self._set_background_color()

    def keyPressEvent(self, event):
        """
        Detects a key press event and redispatch to the correct
        movement.
        """
        if event.key() == Qt.Key.Key_Up:
            if Qt.KeyboardModifier.ControlModifier in event.modifiers():
                self.move_stage(direction=Direction.zup)
            else:
                self.move_stage(direction=Direction.up)
        elif event.key() == Qt.Key.Key_Down:
            if Qt.KeyboardModifier.ControlModifier in event.modifiers():
                self.move_stage(direction=Direction.zdown)
            else:
                self.move_stage(direction=Direction.down)
        elif event.key() == Qt.Key.Key_Left:
            self.move_stage(direction=Direction.left)
        elif event.key() == Qt.Key.Key_Right:
            self.move_stage(direction=Direction.right)
        else:
            super().keyPressEvent(event)
