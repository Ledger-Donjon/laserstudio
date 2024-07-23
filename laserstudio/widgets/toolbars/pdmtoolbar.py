from PyQt6.QtWidgets import (
    QPushButton,
    QLabel,
    QGridLayout,
    QWidget,
    QSpinBox,
    QDoubleSpinBox,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap

from laserstudio.instruments.pdm import PDMInstrument
from ...utils.util import resource_path, colored_image
from typing import TYPE_CHECKING
from ..return_line_edit import ReturnDoubleSpinBox
from .lasertoolbar import LaserToolbar

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class PDMToolbar(LaserToolbar):
    def __init__(self, laser_studio: "LaserStudio", laser_num: int):
        assert laser_num < len(laser_studio.instruments.lasers)
        self.laser = laser_studio.instruments.lasers[laser_num]
        assert isinstance(self.laser, PDMInstrument)
        super().__init__(f"Laser {laser_num} (PDM)", "pdm", laser_num)
        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
        )

        self.setFloatable(True)
        w = QPushButton(self)
        w.setToolTip("On/Off Laser")
        w.setCheckable(True)
        w.setChecked(False)
        icon = QIcon()
        icon.addPixmap(
            QPixmap(resource_path(":/icons/laser-on.svg")),
            QIcon.Mode.Normal,
            QIcon.State.On,
        )
        icon.addPixmap(
            QPixmap(colored_image(":/icons/laser-off.svg")),
            QIcon.Mode.Normal,
            QIcon.State.Off,
        )
        w.setIcon(icon)
        w.setIconSize(QSize(24, 24))
        w.toggled.connect(lambda b: self.laser.__setattr__("on_off", b))
        self.addWidget(w)

        grid = QGridLayout()
        row = 0

        # Laser pulsed power
        grid.addWidget(QLabel("Pulse power:"), row, 0)
        w = self.pulse_power_input = ReturnDoubleSpinBox()
        w.setMinimum(0.0)
        w.setMaximum(100.0)
        w.setSuffix("%")
        w.setValue(0)
        w.returnPressed.connect(
            lambda: self.laser.__setattr__(
                "current_percentage", self.pulse_power_input.value()
            )
        )
        grid.addWidget(w, row, 1)
        row += 1

        # Pulse power sweeping
        grid.addWidget(QLabel("Sweep min power:"), row, 0)
        w = self.sweep_min_input = QDoubleSpinBox()
        w.setMinimum(0.0)
        w.setMaximum(100.0)
        w.setSuffix("%")
        w.setValue(0)
        w.valueChanged.connect(
            lambda: self.laser.__setattr__("sweep_min", self.sweep_min_input.value())
        )
        grid.addWidget(w, row, 1)
        row += 1

        grid.addWidget(QLabel("Sweep max power:"), row, 0)
        w = self.sweep_max_input = QDoubleSpinBox()
        w.setMinimum(0.0)
        w.setMaximum(100.0)
        w.setSuffix("%")
        w.setValue(0)
        w.valueChanged.connect(
            lambda: self.laser.__setattr__("sweep_max", self.sweep_max_input.value())
        )
        grid.addWidget(w, row, 1)
        row += 1
        grid.addWidget(QLabel("Sweep frequency:"), row, 0)
        w = self.sweep_freq_input = QSpinBox()
        w.setMinimum(1)
        w.setMaximum(10000)
        w.setValue(10)
        w.valueChanged.connect(
            lambda: self.laser.__setattr__("sweep_freq", self.sweep_freq_input.value())
        )

        grid.addWidget(w, row, 1)
        row += 1

        # Laser offset current
        grid.addWidget(QLabel("Offset current:"), row, 0)
        w = self.offset_current_input = ReturnDoubleSpinBox()
        w.setMinimum(0.0)
        w.setMaximum(150.0)  # TODO read limit from pypdm if possible
        w.setDecimals(3)
        w.setSuffix("mA")
        w.setValue(0)
        w.returnPressed.connect(
            lambda: self.laser.__setattr__(
                "offset_current", self.offset_current_input.value()
            )
        )
        grid.addWidget(w, row, 1)
        row += 1

        w = QWidget()
        w.setLayout(grid)
        self.addWidget(w)

        self.reload_parameters()

    def reload_parameters(self):
        # To prevent boxes changing to Blue
        self.pulse_power_input.blockSignals(True)
        self.offset_current_input.blockSignals(True)

        self.pulse_power_input.setValue(self.laser.current_percentage)
        self.sweep_min_input.setValue(self.laser.sweep_min)
        self.sweep_max_input.setValue(self.laser.sweep_max)
        self.sweep_freq_input.setValue(self.laser.sweep_freq)
        self.offset_current_input.setValue(self.laser.offset_current)

        self.pulse_power_input.blockSignals(False)
        self.offset_current_input.blockSignals(False)
