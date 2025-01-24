from PyQt6.QtWidgets import QPushButton, QToolBar, QSlider, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap
from ...utils.util import colored_image
from ...utils.colors import LedgerColors

from ...instruments.hayashilight import HayashiLRInstrument


class HayashiLightToolbar(QToolBar):
    def __init__(self, hyshlr: HayashiLRInstrument):
        """
        :param hyshlr: Hayashi Light instrument to be controlled by the toolbar.
        """
        self.hyshlr = hyshlr

        super().__init__(hyshlr.label)
        self.setObjectName("toolbar-hayashi-light")  # For settings save and restore

        self.setAllowedAreas(Qt.ToolBarArea.AllToolBarAreas)
        self.setFloatable(True)

        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        w = QWidget()
        w.setLayout(hbox)
        self.addWidget(w)

        w = QPushButton(self)

        w.setToolTip("On/Off Light")
        w.setCheckable(True)
        w.setChecked(False)
        icon = QIcon()
        icon.addPixmap(
            QPixmap(
                colored_image(
                    ":/icons/fontawesome-free/lightbulb-regular.svg",
                    LedgerColors.SafetyOrange,
                )
            ),
            QIcon.Mode.Normal,
            QIcon.State.On,
        )
        icon.addPixmap(
            QPixmap(colored_image(":/icons/fontawesome-free/lightbulb-regular.svg")),
            QIcon.Mode.Normal,
            QIcon.State.Off,
        )
        w.setIcon(icon)
        w.setIconSize(QSize(24, 24))
        w.toggled.connect(lambda b: self.hyshlr.hyslr.__setattr__("lamp", b))
        hbox.addWidget(w)

        w = QSlider(Qt.Orientation.Horizontal, self)
        w.setRange(0, 100)
        w.setValue(0)
        w.setToolTip("Intensity of the light")
        w.setSingleStep(10)
        w.valueChanged.connect(
            lambda v: self.hyshlr.hyslr.__setattr__("intensity", float(v) / 100.0)
        )
        hbox.addWidget(w)
