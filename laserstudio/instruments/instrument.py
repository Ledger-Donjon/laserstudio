from PyQt6.QtCore import QObject, pyqtSignal, QVariant


class Instrument(QObject):
    # Signal emitted when the instrument has a parameter which changed in another way than UI interface
    parameter_changed = pyqtSignal(str, QVariant)

    def __init__(self, config: dict):
        super().__init__()
        self.label = config.get("label")
