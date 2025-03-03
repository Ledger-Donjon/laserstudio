from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QStyleFactory
from PyQt6.QtCore import Qt
from enum import Enum


class LedgerColors(Enum):
    SafetyOrange = QColor(255, 83, 0)
    SerenityPurple = QColor(212, 160, 255)
    SecurityBlue = QColor(0, 27, 60)
    Grellow = QColor(222, 255, 0)


LedgerPalette = QPalette()

LedgerPalette.setColor(QPalette.ColorRole.Window, QColor(25, 25, 25))
LedgerPalette.setColor(QPalette.ColorRole.WindowText, QColor(240, 240, 240))

LedgerPalette.setColor(QPalette.ColorRole.Base, QColor(50, 50, 50))
LedgerPalette.setColor(
    QPalette.ColorRole.AlternateBase, LedgerColors.SafetyOrange.value
)

LedgerPalette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
LedgerPalette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)

LedgerPalette.setColor(QPalette.ColorRole.PlaceholderText, Qt.GlobalColor.darkGray)
LedgerPalette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.lightGray)

LedgerPalette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
LedgerPalette.setColor(QPalette.ColorRole.ButtonText, QColor(200, 200, 200))

LedgerPalette.setColor(QPalette.ColorRole.BrightText, LedgerColors.SafetyOrange.value)

LedgerPalette.setColor(QPalette.ColorRole.Highlight, LedgerColors.SafetyOrange.value)
LedgerPalette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))

LedgerPalette.setColor(QPalette.ColorRole.Link, LedgerColors.SafetyOrange.value)

# # Disabled colors are just darker
roles = [
    QPalette.ColorRole.WindowText,
    QPalette.ColorRole.Base,
    QPalette.ColorRole.AlternateBase,
    QPalette.ColorRole.ToolTipText,
    QPalette.ColorRole.PlaceholderText,
    QPalette.ColorRole.Button,
    QPalette.ColorRole.ButtonText,
    QPalette.ColorRole.Text,
    QPalette.ColorRole.BrightText,
    QPalette.ColorRole.HighlightedText,
    QPalette.ColorRole.Link,
]
for role in roles:
    c = LedgerPalette.color(role)
    LedgerPalette.setColor(
        QPalette.ColorGroup.Disabled,
        role,
        c.darker(150),
    )

LedgerStyle = QStyleFactory.create("Fusion")
