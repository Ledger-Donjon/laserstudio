from PyQt6.QtCore import QObject, pyqtSignal, QVariant


class Instrument(QObject):
    # Signal emitted when the instrument has a parameter which changed in another way than UI interface
    parameter_changed = pyqtSignal(str, QVariant)
