from PyQt6.QtGui import QColor, QPalette, QIcon, QPainter
from PyQt6.QtWidgets import (
    QStyleFactory,
    QProxyStyle,
    QStyle,
    QStyleOptionButton,
    QStyleOption,
    QWidget,
)
from PyQt6.QtCore import Qt, QRect
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


class LedgerProxyStyle(QProxyStyle):
    def __init__(self, base_style: QStyle | None = None, icon_text_spacing: int = 8):
        super().__init__(base_style or QStyleFactory.create("Fusion"))
        self.icon_text_spacing = icon_text_spacing

    def drawControl(
        self,
        element: QStyle.ControlElement,
        option: QStyleOption | None,
        painter: QPainter | None,
        widget: QWidget | None = None,
    ) -> None:
        if option is None or painter is None:
            super().drawControl(element, option, painter, widget)
            return
        if (
            element == QStyle.ControlElement.CE_PushButtonLabel
            and isinstance(option, QStyleOptionButton)
            and not option.icon.isNull()
            and option.text
        ):
            contents = self.subElementRect(
                QStyle.SubElement.SE_PushButtonContents, option, widget
            )

            icon_size = option.iconSize
            fm = option.fontMetrics

            available_text_width = max(
                0, contents.width() - icon_size.width() - self.icon_text_spacing
            )
            display_text = fm.elidedText(
                option.text, Qt.TextElideMode.ElideRight, available_text_width
            )
            display_text_width = min(
                available_text_width, fm.horizontalAdvance(display_text)
            )

            total_width = (
                icon_size.width() + self.icon_text_spacing + display_text_width
            )
            alignment = Qt.AlignmentFlag.AlignHCenter
            if alignment & Qt.AlignmentFlag.AlignHCenter:
                start_x = contents.x() + (contents.width() - total_width) // 2
            elif alignment & Qt.AlignmentFlag.AlignRight:
                start_x = contents.right() - total_width + 1
            else:
                start_x = contents.x()

            center_y = contents.y() + contents.height() // 2
            icon_rect = QRect(
                start_x,
                center_y - icon_size.height() // 2,
                icon_size.width(),
                icon_size.height(),
            )
            text_rect = QRect(
                start_x + icon_size.width() + self.icon_text_spacing,
                center_y - fm.height() // 2,
                available_text_width,
                fm.height(),
            )

            icon_rect = self.visualRect(option.direction, contents, icon_rect)
            text_rect = self.visualRect(option.direction, contents, text_rect)

            if option.state & QStyle.StateFlag.State_Enabled:
                if option.state & QStyle.StateFlag.State_MouseOver:
                    icon_mode = QIcon.Mode.Active
                else:
                    icon_mode = QIcon.Mode.Normal
            else:
                icon_mode = QIcon.Mode.Disabled
            icon_state = (
                QIcon.State.On
                if option.state & QStyle.StateFlag.State_On
                else QIcon.State.Off
            )

            option.icon.paint(
                painter, icon_rect, Qt.AlignmentFlag.AlignCenter, icon_mode, icon_state
            )
            self.drawItemText(
                painter,
                text_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                option.palette,
                bool(option.state & QStyle.StateFlag.State_Enabled),
                display_text,
                QPalette.ColorRole.ButtonText,
            )
            return

        super().drawControl(element, option, painter, widget)


LedgerStyle = LedgerProxyStyle()
