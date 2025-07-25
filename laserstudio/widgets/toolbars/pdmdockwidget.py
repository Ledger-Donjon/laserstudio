from typing import Any
from PyQt6.QtWidgets import (
    QPushButton,
    QLabel,
    QGridLayout,
    QWidget,
    QSpinBox,
    QDoubleSpinBox,
    QDockWidget,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap
from ...instruments.pdm import PDMInstrument
from ...utils.util import resource_path, colored_image
from ..return_line_edit import ReturnDoubleSpinBox
from ..coloredbutton import ColoredPushButton


class PDMDockWidget(QDockWidget):
    def __init__(self, laser: PDMInstrument, laser_num: int):
        """
        :param laser: Alphanov PDM instrument.
        :param laser_num: Laser equipment index.
        """
        assert isinstance(laser, PDMInstrument)
        self.laser = laser
        super().__init__(f"Laser {laser_num} (PDM)")

        if self.laser.label is not None:
            self.setWindowTitle(f"Laser {laser_num} (PDM) - " + self.laser.label)

        self.setObjectName(
            f"toolbox-laser-pdm-{laser_num}"
        )  # For settings save and restore

        w = QWidget()
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.setWidget(w)

        grid = QGridLayout()
        w.setLayout(grid)
        grid.setContentsMargins(0, 4, 0, 0)
        row = 0

        w = self.on_off_button = QPushButton(self)
        if self.laser.label is not None:
            self.setWindowTitle(self.laser.label)
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
        grid.addWidget(w, row, 0, 1, 2)
        row += 1

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
        w.setSuffix("\xa0mA")
        w.setValue(0)
        w.returnPressed.connect(
            lambda: self.laser.__setattr__(
                "offset_current", self.offset_current_input.value()
            )
        )
        grid.addWidget(w, row, 1)
        row += 1

        # Laser shutter
        if self.laser.shutter is not None:
            grid.addWidget(QLabel("Shutter:"), row, 0)
            w = ColoredPushButton(
                ":/icons/shutter-open.svg", ":/icons/shutter-closed.svg"
            )
            w.setToolTip("Open/Close shutter")
            w.setCheckable(True)
            w.setChecked(False)
            w.setIconSize(QSize(24, 24))
            w.toggled.connect(self.open_shutter)
            grid.addWidget(w, row, 1)
            row += 1

        # Laser interlock status
        grid.addWidget(QLabel("Interlock status:"), row, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeading)
        self.interlock_label = w = QLabel("Unknown")
        grid.addWidget(w, row, 1, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeading)
        row += 1

        self.reload_parameters()
        self.laser.parameter_changed.connect(self.refresh_interface)

    def open_shutter(self, b):
        if self.laser.shutter is not None:
            self.laser.shutter.open = b

    def refresh_interface(self, name: str, value: Any):
        """Refresh the ToolBar UI according to given parameter and value"""
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
            self.interlock_label.setText("Opened" if value else "Closed")

    def reload_parameters(self):
        self.sweep_min_input.setValue(self.laser.sweep_min)
        self.sweep_max_input.setValue(self.laser.sweep_max)
        self.sweep_freq_input.setValue(self.laser.sweep_freq)
        self.refresh_interface("current_percentage", self.laser.current_percentage)
        self.refresh_interface("offset_current", self.laser.offset_current)
        self.refresh_interface("interlock_status", self.laser.interlock_status)