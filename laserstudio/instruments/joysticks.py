import os

from PyQt6.QtCore import pyqtSignal, QObject, QThread
import struct


class JoystickThread(QThread):
    def __init__(self, joystick: "JoystickInstrument"):
        super(JoystickThread, self).__init__()
        self.joystick = joystick

    def run(self):
        while not self.isInterruptionRequested():
            if evbuf := self.joystick.device.read(8):
                time, value, type, number = struct.unpack("IhBB", evbuf)
                if type & 0x01:
                    # Filter out buttons different from 4 and 5
                    if number not in [4, 5]:
                        continue
                    self.joystick.button_pressed.emit(number, bool(value))
                elif type & 0x02:
                    # Filter out axes different from 0 and 1
                    if number not in [0, 1]:
                        continue
                    fvalue = value / 32767.0
                    if number == 1:
                        fvalue = -fvalue
                    self.joystick.axis_changed.emit(number, fvalue)


class JoystickInstrument(QObject):
    button_pressed = pyqtSignal(int, bool)
    axis_changed = pyqtSignal(int, float)

    def __init__(self, dev: str):
        """Creation of a specific thread for listening on port"""
        super(JoystickInstrument, self).__init__()
        self.device = open(dev, "rb")
        os.set_blocking(self.device.fileno(), False)
        self.joy_thread = JoystickThread(self)
        self.joy_thread.setTerminationEnabled(True)
        self.joy_thread.start()

    def stop(self):
        self.joy_thread.requestInterruption()
        self.device.close()
