from PyQt6.QtCore import pyqtBoundSignal
from PyQt6.QtWidgets import QLineEdit, QDoubleSpinBox, QSpinBox


class ReturnLineEdit(QLineEdit):
    """
    A QLineEdit where the appearance change while it is being edited, and resets
    when Return key is pressed.
    """

    def __init__(self):
        super().__init__()
        self.textEdited.connect(self.highlight)
        self.returnPressed.connect(self.reset)

    def highlight(self):
        self.setStyleSheet("background: #344266;")

    def reset(self):
        self.setStyleSheet("")


class ReturnDoubleSpinBox(QDoubleSpinBox):
    """
    A QSpinDoubleSpinbox where the appearance change
    while it is being edited, and resets when Return key is pressed.
    """

    def __init__(self):
        super().__init__()
        self.setLineEdit(le := ReturnLineEdit())
        self.valueChanged.connect(le.highlight)

    @property
    def returnPressed(self) -> pyqtBoundSignal:
        # To access easily to the returnPressed signal
        assert (le := self.lineEdit()) is not None
        return le.returnPressed

    @property
    def reset(self):
        assert isinstance(le := self.lineEdit(), ReturnLineEdit)
        return le.reset


class ReturnSpinBox(QSpinBox):
    """
    A QSpinSpinbox where the appearance change
    while it is being edited, and resets when Return key is pressed.
    """

    def __init__(self):
        super().__init__()
        self.setLineEdit(le := ReturnLineEdit())
        self.valueChanged.connect(le.highlight)

    @property
    def returnPressed(self) -> pyqtBoundSignal:
        # To access easily to the returnPressed signal
        assert (le := self.lineEdit()) is not None
        return le.returnPressed

    @property
    def reset(self):
        assert isinstance(le := self.lineEdit(), ReturnLineEdit)
        return le.reset
