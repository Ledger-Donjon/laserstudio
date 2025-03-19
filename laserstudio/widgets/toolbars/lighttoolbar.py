from PyQt6.QtWidgets import QPushButton, QToolBar, QSlider, QHBoxLayout, QWidget, QLabel
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap
from ...utils.util import colored_image
from ...utils.colors import LedgerColors

from ...instruments.light import LightInstrument
from ...instruments.hayashilight import HayashiLRInstrument


class LightToolbar(QToolBar):
    def __init__(self, light: LightInstrument):
        """
        :param light: Light instrument to be controlled by the toolbar.
        """
        self.light = light

        super().__init__(light.label)
        self.setObjectName("toolbar-light")  # For settings save and restore

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
        w.toggled.connect(lambda b: self.light.__setattr__("lamp_enabled", b))
        hbox.addWidget(w)

        w = QSlider(Qt.Orientation.Horizontal, self)
        w.setRange(0, 100)
        w.setValue(0)
        w.setToolTip("Intensity of the light")
        w.setSingleStep(10)
        w.valueChanged.connect(
            lambda v: self.light.__setattr__("intensity", float(v) / 100.0)
        )
        hbox.addWidget(w)

        if type(light) is HayashiLRInstrument:
            w = self.label_burnout = QLabel("Lamp burnout!")
            w.setStyleSheet("color: red")
            w.setVisible(light.hyslr.burnout)
            self.addWidget(w)
