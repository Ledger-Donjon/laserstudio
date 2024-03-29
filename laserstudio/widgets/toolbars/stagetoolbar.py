from typing import TYPE_CHECKING, Optional, Union
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QToolBar,
    QPushButton,
    QComboBox,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QWidget,
    QMessageBox,
)
from ...utils.util import colored_image
from ..keyboardbox import KeyboardBox, Direction
from ...instruments.stage import MoveFor, CNCRouter
from ...instruments.joysticks import JoystickInstrument
from ...instruments.joysticksHID import JoystickHIDInstrument, HIDGAMEPAD
import os

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class StageToolbar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio"):
        assert laser_studio.instruments.stage is not None
        self.stage = laser_studio.instruments.stage
        super().__init__("Stage control", laser_studio)
        group = laser_studio.viewer_buttons_group
        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea
            | Qt.ToolBarArea.RightToolBarArea
            | Qt.ToolBarArea.BottomToolBarArea
        )
        self.setFloatable(True)

        w = QWidget()
        vbox = QVBoxLayout()
        w.setLayout(vbox)
        self.addWidget(w)

        hbox = QHBoxLayout()
        vbox.addLayout(hbox)

        # Activate stage-move mode
        w = QPushButton(self)
        w.setToolTip("Move stage mode")
        w.setIcon(QIcon(colored_image(":/icons/fontawesome-free/directions-solid.svg")))
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        hbox.addWidget(w)
        group.addButton(w)
        group.setId(w, laser_studio.viewer.Mode.STAGE)

        self.mem_point_selector = box = QComboBox()
        for i in range(len(self.stage.mem_points)):
            box.addItem(f"Go to M{i}")
        box.activated.connect(
            lambda i: self.stage.move_to(self.stage.mem_points[i], wait=True)
        )
        hbox.addWidget(box)
        box.setHidden(len(self.stage.mem_points) == 0)

        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        w = QPushButton(self)
        w.setText("Home")
        w.clicked.connect(self.home)
        hbox.addWidget(w)

        w = QPushButton(self)
        w.setText("Get Position")
        w.clicked.connect(lambda: print(self.stage.stage.position))
        hbox.addWidget(w)

        if isinstance(self.stage.stage, CNCRouter):
            hbox = QHBoxLayout()
            w = QPushButton(self)
            w.setText("Set Origin")
            w.clicked.connect(self.stage.stage.set_origin)
            hbox.addWidget(w)
            w = QPushButton(self)
            w.setText("Reset GRBL")
            w.clicked.connect(self.stage.stage.reset_grbl)
            hbox.addWidget(w)
            vbox.addLayout(hbox)

        # Keyboard box
        self.keyboardbox = w = KeyboardBox(self.stage)
        self.addWidget(w)

        w = QWidget()
        vbox = QVBoxLayout()
        w.setLayout(vbox)
        self.addWidget(w)

        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        # Move for
        self.move_for_selector = box = QComboBox()
        box.addItem("Camera", userData=MoveFor(MoveFor.Type.CAMERA_CENTER))
        for i in range(len(laser_studio.instruments.lasers)):
            box.addItem(f"Laser {i+1}", userData=MoveFor(MoveFor.Type.LASER, i))
        for i in range(len(laser_studio.instruments.probes)):
            box.addItem(f"Probe {i+1}", userData=MoveFor(MoveFor.Type.PROBE, i))
        box.activated.connect(self.move_for_selection)
        hbox.addWidget(QLabel("Focus on:"))
        hbox.addWidget(box)

        # Joysticks
        self.joystick: Optional[Union[JoystickInstrument, JoystickHIDInstrument]] = None
        input_dir = os.path.join(os.sep, "dev", "input")
        if os.path.exists(input_dir):
            joysticks = [
                fn
                for fn in os.listdir(os.path.join(os.sep, "dev", "input"))
                if fn.startswith("js")
            ]
        else:
            joysticks = ["JoyConL", "JoyConR", "PS4"]

        if len(joysticks):
            hbox = QHBoxLayout()
            w = QComboBox()
            w.addItem("Disabled")
            w.addItems(joysticks)
            w.currentTextChanged.connect(self.activate_joystick)
            hbox.addWidget(QLabel("Joystick:"))
            hbox.addWidget(w)
            vbox.addLayout(hbox)

    def home(self):
        # Request a confirmation from the user
        if QMessageBox.StandardButton.Apply == QMessageBox.warning(
            None,
            "Homing",
            "Caution: Homing can make some collision and break your setup."
            " Make sure that your setup is ready to perform this operation.",
            buttons=QMessageBox.StandardButton.Abort | QMessageBox.StandardButton.Apply,
            defaultButton=QMessageBox.StandardButton.Abort,
        ):
            ...
            # self.stage.stage.home(wait=True)

    def move_for_selection(self, index: int):
        move_for = self.move_for_selector.itemData(index, Qt.ItemDataRole.UserRole)
        if not isinstance(move_for, MoveFor):
            return
        self.stage.move_for = move_for

    def activate_joystick(self, name: str):
        """
        Creates a JoystickInstrument associated with the given device name

        :param name: the name of the device associated to the JoystickInstrument (in `/dev/input/`),
            starting by `js`.
        """
        if self.joystick is not None:
            self.joystick.stop()
            self.joystick = None
        if name.startswith("js"):
            self.joystick = JoystickInstrument(
                os.path.join(os.sep, "dev", "input", name)
            )
        if name == "JoyConR":
            self.joystick = JoystickHIDInstrument(HIDGAMEPAD.JOYCON_R)
        if name == "JoyConL":
            self.joystick = JoystickHIDInstrument(HIDGAMEPAD.JOYCON_L)
        if name == "PS4":
            self.joystick = JoystickHIDInstrument(HIDGAMEPAD.PS4)
        if self.joystick is not None:
            self.joystick.axis_changed.connect(self.joystick_axis)
            self.joystick.button_pressed.connect(self.joystick_button)

    def joystick_button(self, button: int, pressed: bool):
        """
        Called to handle the Joystick's pressure of a button

        :param button: the button's number
        :param pressed: True if the button has been pressed, False if it has been released
        """
        if not pressed:
            return
        axe = button // 2
        if axe != 2:
            return
        coefficient = (button % 2) * 2.0 - 1.0
        self.joystick_axis(axe, coefficient)

    def joystick_axis(self, axe: int, coefficient: float):
        """
        Called to handle the Joystick's change of value of an axe

        :param axe: the axe of the joystick which has changed
        :param coefficient: The new value of the axe (from 0 to 1)
        """
        if axe >= self.stage.stage.num_axis:
            return
        if abs(coefficient) < 0.001:
            return

        if axe == 0:
            self.keyboardbox.move_stage(
                direction=Direction.right if coefficient > 0 else Direction.left
            )
        elif axe == 1:
            self.keyboardbox.move_stage(
                direction=Direction.up if coefficient > 0 else Direction.down
            )
        elif axe == 2:
            self.keyboardbox.move_stage(
                direction=Direction.zup if coefficient > 0 else Direction.zdown
            )
