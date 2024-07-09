from PyQt6.QtWidgets import QWidget, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QColor
from typing import Optional, Union
from ..utils.util import colored_image
from ..utils.colors import LedgerColors


class ColoredPushButton(QPushButton):
    def __init__(
        self,
        icon_path: str,
        color: Union[
            QColor, Qt.GlobalColor, int, LedgerColors
        ] = LedgerColors.SafetyOrange,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.normal_pixmap = colored_image(icon_path)
        self.colored_pixmap = colored_image(icon_path, color=color)
        icon = QIcon()
        icon.addPixmap(self.normal_pixmap, QIcon.Mode.Normal, QIcon.State.Off)
        icon.addPixmap(self.colored_pixmap, QIcon.Mode.Normal, QIcon.State.On)
        self.setIcon(icon)
