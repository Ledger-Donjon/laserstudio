from PyQt6.QtCore import pyqtSignal, QObject, QThread
from enum import Enum, auto
from typing import Optional
import hid


class Button(Enum):
    Left = auto()
    Right = auto()
    Up = auto()
    Down = auto()
    Zup = auto()
    Zdown = auto()


class HIDGAMEPAD(Enum):
    JOYCON_R = auto()
    JOYCON_L = auto()
    PS4 = auto()

    @property
    def vid_pid(self) -> tuple[int, int]:
        if self == HIDGAMEPAD.JOYCON_R:
            return (0x057E, 0x2007)
        if self == HIDGAMEPAD.JOYCON_L:
            return (0x057E, 0x2006)
        if self == HIDGAMEPAD.PS4:
            return (0x054C, 0x09CC)
        raise Exception


class JoystickHIDThread(QThread):
    def __init__(self, joystick: "JoystickHIDInstrument"):
        super(JoystickHIDThread, self).__init__()
        self.joystick = joystick

    def run(self):
        while not self.isInterruptionRequested():
            if self.joystick.device is None:
                continue
            try:
                if report := self.joystick.device.read(64):
                    self.joystick.update_report(report)
            except OSError:
                # Read error
                self.joystick.stop()


BUTTON_POSITON = {
    HIDGAMEPAD.JOYCON_L: {
        Button.Left: (1, 4),
        Button.Right: (1, 2),
        Button.Up: (1, 8),
        Button.Down: (1, 1),
        Button.Zup: (1, 32),
        Button.Zdown: (1, 16),
    },
    HIDGAMEPAD.JOYCON_R: {
        Button.Left: (5, 2),
        Button.Right: (5, 1),
        Button.Up: (5, 4),
        Button.Down: (5, 8),
        Button.Zup: (5, 16),
        Button.Zdown: (5, 32),
    },
    HIDGAMEPAD.PS4: {
        Button.Zup: (8, 2),
        Button.Zdown: (8, 1),
    },
}


class JoystickHIDInstrument(QObject):
    button_pressed = pyqtSignal(int, bool)
    axis_changed = pyqtSignal(int, float)

    def __init__(self, type: HIDGAMEPAD):
        """Creation of a specific thread for listening on port"""
        super().__init__()
        self.device_type = type
        self.device = None

        self.joy_thread = JoystickHIDThread(self)
        self.joy_thread.setTerminationEnabled(True)
        self.joy_thread.start()

        self.report = [0] * 6

        self.buttons_states = {
            Button.Left: False,
            Button.Right: False,
            Button.Down: False,
            Button.Up: False,
            Button.Zdown: False,
            Button.Zup: False,
        }
        self.open()

    def stop(self):
        self.joy_thread.requestInterruption()
        if self.device is not None:
            self.device.close()
            self.device = None

    def open(self):
        if self.device is None:
            self.device = hid.device()
        else:
            self.device.close()
        try:
            self.device.open(*self.device_type.vid_pid)
        except OSError:
            # Open failed
            self.device = None

    def is_pressed(self, button: Button) -> bool:
        if self.device_type == HIDGAMEPAD.PS4:
            if button in [Button.Up, Button.Down, Button.Left, Button.Right]:
                return button in {
                    0: [Button.Up],
                    1: [Button.Up, Button.Right],
                    2: [Button.Right],
                    3: [Button.Down, Button.Right],
                    4: [Button.Down],
                    5: [Button.Down, Button.Left],
                    6: [Button.Left],
                    7: [Button.Up, Button.Left],
                }.get(self.report[7], [])

        index, mask = BUTTON_POSITON[self.device_type][button]
        return bool(self.report[index] & mask)

    def update_report(self, report: list[int]):
        self.report = report
        for b in Button:
            pressed = self.is_pressed(b)
            if self.buttons_states[b] != pressed:
                if b == Button.Up:
                    self.axis_changed.emit(1, 1.0 if pressed else 0.0)
                elif b == Button.Down:
                    self.axis_changed.emit(1, -1.0 if pressed else 0.0)
                elif b == Button.Left:
                    self.axis_changed.emit(0, -1.0 if pressed else 0.0)
                elif b == Button.Right:
                    self.axis_changed.emit(0, 1.0 if pressed else 0.0)
                elif b == Button.Zdown:
                    self.button_pressed.emit(4, pressed)
                elif b == Button.Zup:
                    self.button_pressed.emit(5, pressed)
                self.buttons_states[b] = pressed
