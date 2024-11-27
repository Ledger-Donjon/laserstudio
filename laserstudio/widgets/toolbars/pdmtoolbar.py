from PyQt6.QtWidgets import (
    QPushButton,
    QLabel,
    QGridLayout,
    QWidget,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
)
from PyQt6.QtCore import Qt, QSize, QVariant
from PyQt6.QtGui import QIcon, QPixmap
from typing import Any
from laserstudio.instruments.pdm import PDMInstrument
from ...utils.util import resource_path, colored_image
from ..return_line_edit import ReturnDoubleSpinBox
from PyQt6.QtWidgets import QToolBar


class PDMToolbar(QToolBar):
    def __init__(self, laser: PDMInstrument, laser_num: int):
        """
        :param laser: Alphanov PDM instrument.
        :param laser_num: Laser equipment index.
        """
        assert isinstance(laser, PDMInstrument)
        self.laser = laser
        super().__init__(f"Laser {laser_num} (PDM)")
        self.setObjectName(
            f"toolbox-laser-pdm-{laser_num}"
        )  # For settings save and restore

        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
        )
        self.setFloatable(True)

        w = self.on_off_button = QPushButton(self)
        if self.laser.label is not None:
            w.setText(self.laser.label)
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
        grid.setContentsMargins(0, 4, 0, 0)
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

        # Laser interlock status
        grid.addWidget(QLabel("Interlock status:"), row, 0)
        self.interlock_label = w = QLabel("Unknown")
        grid.addWidget(w, row, 1)
        row += 1

        w = QWidget()
        w.setLayout(grid)
        self.addWidget(w)

        self.reload_parameters()
        self.laser.parameter_changed.connect(self.refresh_interface)

    def refresh_interface(self, name: str, value: Any):
        """Refresh the Toolbar UI according to given parameter and value"""
        if name == "on_off":
            self.on_off_button.blockSignals(True)
            self.on_off_button.setChecked(value)
            self.on_off_button.blockSignals(False)
        elif name == "current_percentage":
            self.pulse_power_input.blockSignals(True)
            self.pulse_power_input.setValue(value)
            self.pulse_power_input.blockSignals(False)
        elif name == "offset_current":
            self.offset_current_input.blockSignals(True)
            self.offset_current_input.setValue(value)
            self.offset_current_input.blockSignals(False)
        elif name == "interlock_status":
            self.interlock_label.setText('Opened' if value else 'Closed')

    def reload_parameters(self):
        self.sweep_min_input.setValue(self.laser.sweep_min)
        self.sweep_max_input.setValue(self.laser.sweep_max)
        self.sweep_freq_input.setValue(self.laser.sweep_freq)
        self.refresh_interface("current_percentage", self.laser.current_percentage)
        self.refresh_interface("offset_current", self.laser.offset_current)
        self.refresh_interface("interlock_status", self.laser.interlock_status)
