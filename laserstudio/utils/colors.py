from PyQt6.QtGui import QColor, QPalette, QIcon, QPainter
from PyQt6.QtWidgets import (
    QStyleFactory,
    QProxyStyle,
    QStyle,
    QStyleOptionButton,
    QStyleOptionToolButton,
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
        if element == QStyle.ControlElement.CE_PushButton and isinstance(
            option, QStyleOptionButton
        ):
            base_option = QStyleOptionButton(option)
            base_option.text = ""
            base_option.icon = QIcon()
            super().drawControl(element, base_option, painter, widget)
            contents = self.subElementRect(
                QStyle.SubElement.SE_PushButtonContents, option, widget
            )
            self._draw_icon_text_label(
                QStyle.ControlElement.CE_PushButtonLabel,
                option,
                painter,
                widget,
                contents,
            )
            return
        if element == QStyle.ControlElement.CE_PushButtonLabel and isinstance(
            option, QStyleOptionButton
        ):
            contents = self.subElementRect(
                QStyle.SubElement.SE_PushButtonContents, option, widget
            )
            self._draw_icon_text_label(element, option, painter, widget, contents)
            return

        if element == QStyle.ControlElement.CE_ToolButtonLabel and isinstance(
            option, QStyleOptionToolButton
        ):
            tool_contents = getattr(
                QStyle.SubElement,
                "SE_ToolButtonContents",
                QStyle.SubElement.SE_PushButtonContents,
            )
            contents = self.subElementRect(tool_contents, option, widget)
            self._draw_icon_text_label(element, option, painter, widget, contents)
            return

        super().drawControl(element, option, painter, widget)

    def _draw_icon_text_label(
        self,
        element: QStyle.ControlElement,
        option: QStyleOptionButton | QStyleOptionToolButton,
        painter: QPainter,
        widget: QWidget | None,
        contents: QRect,
    ) -> None:
        if option.icon.isNull() or not option.text:
            super().drawControl(element, option, painter, widget)
            return

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

        total_width = icon_size.width() + self.icon_text_spacing + display_text_width
        start_x = contents.x() + (contents.width() - total_width) // 2

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

        shift_x = 0
        shift_y = 0
        if option.state & (QStyle.StateFlag.State_Sunken | QStyle.StateFlag.State_On):
            shift_x = self.pixelMetric(
                QStyle.PixelMetric.PM_ButtonShiftHorizontal, option, widget
            )
            shift_y = self.pixelMetric(
                QStyle.PixelMetric.PM_ButtonShiftVertical, option, widget
            )
        if shift_x or shift_y:
            icon_rect.translate(shift_x, shift_y)
            text_rect.translate(shift_x, shift_y)

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
        palette = option.palette
        if (
            widget is not None
            and (option.state & QStyle.StateFlag.State_On)
            and (option.state & QStyle.StateFlag.State_Enabled)
        ):
            checked_color = widget.property("checkedTextColor")
            if isinstance(checked_color, QColor):
                palette = QPalette(palette)
                palette.setColor(QPalette.ColorRole.ButtonText, checked_color)
            elif isinstance(checked_color, str):
                color = QColor(checked_color)
                if color.isValid():
                    palette = QPalette(palette)
                    palette.setColor(QPalette.ColorRole.ButtonText, color)

        text_flags = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        text_flags |= Qt.TextFlag.TextSingleLine
        if self.styleHint(
            QStyle.StyleHint.SH_UnderlineShortcut, option, widget
        ):
            text_flags |= Qt.TextFlag.TextShowMnemonic
        else:
            text_flags |= Qt.TextFlag.TextHideMnemonic

        self.drawItemText(
            painter,
            text_rect,
            text_flags,
            palette,
            bool(option.state & QStyle.StateFlag.State_Enabled),
            display_text,
            QPalette.ColorRole.ButtonText,
        )
        return


LedgerStyle = LedgerProxyStyle()


def ledger_stylesheet() -> str:
    base = LedgerPalette.color(QPalette.ColorRole.Base)
    button = LedgerPalette.color(QPalette.ColorRole.Button)
    text = LedgerPalette.color(QPalette.ColorRole.Text)
    highlight_text = LedgerPalette.color(QPalette.ColorRole.HighlightedText)
    muted = LedgerPalette.color(QPalette.ColorRole.PlaceholderText)

    border = base.darker(140)
    header = base.lighter(110)
    hover = button.lighter(115)
    active = button.lighter(130)
    accent = LedgerColors.SafetyOrange.value
    accent_border = QColor(accent)
    accent_border.setAlpha(70)
    accent_border_rgba = (
        f"rgba({accent_border.red()}, {accent_border.green()}, "
        f"{accent_border.blue()}, {accent_border.alpha()})"
    )

    return f"""
QToolBar {{
    border: 1px solid {border.name()};
    border-radius: 4px;
    margin: 3px;
    padding: 4px;
    background-color: {header.name()};
}}

QToolButton,
QPushButton {{
    background-color: {button.name()};
    color: {text.name()};
    border: 1px solid {border.name()};
    border-radius: 4px;
    padding: 2px 6px;
    min-height: 20px;
}}
QToolButton:hover,
QPushButton:hover {{
    background-color: {hover.name()};
}}
QToolButton:pressed,
QPushButton:pressed {{
    background-color: {active.name()};
}}
QToolButton:checked,
QPushButton:checked {{
    background-color: {active.name()};
    border-color: {accent_border_rgba};
    color: {accent.name()};
}}

QLineEdit,
QComboBox {{
    background-color: {base.name()};
    color: {text.name()};
    border: 1px solid {border.name()};
    border-radius: 3px;
    padding: 1px 4px;
    min-height: 20px;
    selection-background-color: {accent.name()};
    selection-color: {highlight_text.name()};
}}
QLineEdit:focus,
QComboBox:focus {{
    border: 1px solid {accent.name()};
}}

QDockWidget::title {{
    background: {header.name()};
    border: 1px solid {border.name()};
    padding: 4px 6px;
}}

QGroupBox {{
    border: 1px solid {border.name()};
    border-radius: 4px;
    margin-top: 6px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 4px;
    color: {text.name()};
}}

QMenu {{
    background: {base.name()};
    color: {text.name()};
    border: 1px solid {border.name()};
}}
QMenu::item:selected {{
    background: {accent.name()};
    color: {highlight_text.name()};
}}

QStatusBar {{
    background: {header.name()};
    color: {text.name()};
    border-top: 1px solid {border.name()};
}}
QStatusBar::item {{
    border: none;
}}

QLabel#active-mode {{
    padding: 2px 8px;
    border-radius: 4px;
    border: 1px solid {border.name()};
    color: {muted.name()};
    background: {base.name()};
    font-weight: 600;
}}
QLabel#active-mode[modeActive="true"] {{
    border-color: {accent.name()};
    color: {accent.name()};
    background: {header.name()};
}}

QSlider::groove:horizontal {{
    height: 4px;
    background: {border.name()};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {accent.name()};
    border-radius: 2px;
}}
QSlider::add-page:horizontal {{
    background: {border.name()};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 10px;
    margin: -4px 0;
    background: {accent.name()};
    border-radius: 5px;
}}
""".strip()
