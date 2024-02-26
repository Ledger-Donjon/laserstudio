from PyQt6.QtWidgets import QLineEdit


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
