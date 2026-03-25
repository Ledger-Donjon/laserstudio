from PyQt6.QtWidgets import (
    QDockWidget,
    QSlider,
    QHBoxLayout,
    QWidget,
    QLabel,
    QVBoxLayout,
)
from PyQt6.QtCore import Qt, QSize
from ...utils.colors import LedgerColors
from ..coloredbutton import ColoredPushButton
from ...instruments.light import LightInstrument
from ...instruments.hayashilight import HayashiLRInstrument
from ...instruments.lmscontroller import LMSControllerInstrument


class LightDockWidget(QDockWidget):
    def __init__(self, light: LightInstrument):
        """
        :param light: Light instrument to be controlled by the toolbar.
        """
        self.light = light

        super().__init__("Lighting Parameters")

        if self.light.label:
            self.setWindowTitle(self.windowTitle() + " - " + self.light.label)

        self.setObjectName("toolbar-light")  # For settings save and restore

        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)

        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        w = QWidget()
        vbox = QVBoxLayout()
        w.setLayout(vbox)
        self.setWidget(w)
        vbox.addLayout(hbox)

        w = ColoredPushButton(
            icon_path=":/icons/fontawesome-free/lightbulb-regular.svg",
            color=LedgerColors.SafetyOrange.value,
        )
        w.setToolTip("On/Off Light")
        w.setCheckable(True)
        w.setChecked(self.light.light)
        w.setIconSize(QSize(24, 24))
        w.toggled.connect(lambda b: self.light.__setattr__("light", b))
        hbox.addWidget(w)

        w = QSlider(Qt.Orientation.Horizontal, self)
        w.setRange(0, 100)
        w.setValue(int(self.light.intensity * 100))
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
            vbox.addWidget(w)

        if type(light) is LMSControllerInstrument:
            w = ColoredPushButton(
                ":/icons/shutter-closed.svg", ":/icons/shutter-open.svg"
            )
            w.setToolTip("Open/Close shutter")
            w.setCheckable(True)
            w.setChecked(False)
            w.setIconSize(QSize(24, 24))
            w.toggled.connect(self.open_shutter)
            hbox.addWidget(w)
            
        # Add stretch on last row
        vbox.addStretch()

    def open_shutter(self, b):
        if type(self.light) is LMSControllerInstrument:
            self.light.open = b
