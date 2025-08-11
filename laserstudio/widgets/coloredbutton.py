from PyQt6.QtWidgets import QWidget, QPushButton
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QIcon, QColor
from typing import Optional, Union
from ..utils.util import colored_image
from ..utils.colors import LedgerColors


class ColoredPushButton(QPushButton):
    def __init__(
        self,
        icon_path: Optional[str] = None,
        pushed_icon_path: Optional[str] = None,
        color: Union[
            QColor, Qt.GlobalColor, int, LedgerColors
        ] = LedgerColors.SafetyOrange,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        if isinstance(color, LedgerColors):
            color = color.value
        if not isinstance(color, QColor):
            color = QColor(color)
        self.color = color

        if icon_path is not None:
            self.normal_pixmap = colored_image(icon_path)
            self.colored_pixmap = colored_image(
                pushed_icon_path or icon_path, color=color
            )
            icon = QIcon()
            icon.addPixmap(self.normal_pixmap, QIcon.Mode.Normal, QIcon.State.Off)
            icon.addPixmap(self.colored_pixmap, QIcon.Mode.Normal, QIcon.State.On)
            self.setIcon(icon)

    def changeEvent(self, e: Optional[QEvent]) -> None:
        value = super().changeEvent(e)
        color_hex = self.color.getRgb()
        color_hex = f"#{color_hex[0]:02x}{color_hex[1]:02x}{color_hex[2]:02x}"
        self.setStyleSheet(f"QPushButton::checked{{color: {color_hex};}} ")
        return value
