from typing import Any
from PyQt6.QtWidgets import (
    QPushButton,
    QLabel,
    QGridLayout,
    QWidget,
    QSpinBox,
    QDoubleSpinBox,
    QDockWidget,
    QComboBox,
    QGroupBox,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap
from ...instruments.pdm import PDMInstrument, SyncSource, DelayLineType, InterlockStatus
from ...utils.util import resource_path, colored_image
from ..return_line_edit import ReturnDoubleSpinBox, ReturnSpinBox
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
        w.setMaximum(1000000)
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

        grid.addWidget(QLabel("Refresh interval:"), row, 0)
        w = self.refresh_interval_input = ReturnSpinBox()
        w.setSuffix("\xa0ms")
        w.setMinimum(1000)
        w.setMaximum(1000000)
        w.setValue(2000)
        w.valueChanged.connect(
            lambda: self.laser.__setattr__(
                "refresh_interval", self.refresh_interval_input.value()
            )
        )
        grid.addWidget(w, row, 1)
        row += 1


        # Laser's temperature
        grid.addWidget(
            QLabel("Temperature:"),
            row,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeading,
        )
        self.temperature_label = w = QLabel("Unknown")
        grid.addWidget(
            w, row, 1, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeading
        )
        row += 1

        # Laser interlock status
        grid.addWidget(
            QLabel("Interlock status:"),
            row,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeading,
        )
        self.interlock_label = w = QLabel("Unknown")
        grid.addWidget(
            w, row, 1, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeading
        )
        row += 1

        # Pulse width and delay line type
        grid.addWidget(
            QLabel("Pulse width and delay:"),
            row,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeading,
        )
        self.delay_line_type_combobox = w = QComboBox()
        w.addItem("From external (SMA connector)", DelayLineType.NONE)
        w.addItem("From internal parameters", DelayLineType.INTERNAL)
        w.currentIndexChanged.connect(
            lambda: self.laser.__setattr__("delay_line_type", self.delay_line_type_combobox.currentData())
        )
        grid.addWidget(w, row, 1, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeading)
        row += 1

        # Pulse width
        grid.addWidget(QLabel("Pulse width:"), row, 0)
        w = self.pulse_width_input = ReturnSpinBox()
        w.setMinimum(0)
        w.setMaximum(1275000)
        w.setSuffix("\xa0ps")
        w.returnPressed.connect(
            lambda: self.laser.__setattr__("pulse_width", self.pulse_width_input.value())
        )
        grid.addWidget(w, row, 1)
        row += 1

        # Delay
        grid.addWidget(QLabel("Delay:"), row, 0)
        w = self.delay_input = ReturnSpinBox()
        w.setMinimum(0)
        w.setMaximum(15000)
        w.setSuffix("\xa0ps")
        w.returnPressed.connect(
            lambda: self.laser.__setattr__("delay", self.delay_input.value())
        )
        grid.addWidget(w, row, 1)
        row += 1

        advanced_groupbox = QGroupBox("Advanced features")
        self.advanced_layout = advanced_layout = QGridLayout()
        advanced_groupbox.setLayout(advanced_layout)
        advanced_groupbox.setToolTip("Advanced features of the PDM laser")
        advanced_groupbox.setCheckable(True)
        advanced_groupbox.setChecked(False)
        # advanced_groupbox.setVisible(False)
        grid.addWidget(advanced_groupbox, row, 0, 1, 2)
        adv_row = 0
        row += 1
        # After this, all "advanced" widgets use advanced_layout and adv_row
        # Synchronization source
        advanced_layout.addWidget(
            QLabel("Synchronization source:"),
            adv_row,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeading,
        )
        self.sync_source_combobox = w = QComboBox()
        w.addItem("External TTL/LVTTL", SyncSource.EXTERNAL_TTL_LVTTL)
        w.addItem("External LVDS", SyncSource.EXTERNAL_LVDS)
        w.addItem("Internal", SyncSource.INTERNAL)
        w.currentIndexChanged.connect(
            lambda: self.laser.pdm.__setattr__("sync_source", self.sync_source_combobox.currentData())
        )
        advanced_layout.addWidget(w, adv_row, 1, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeading)
        adv_row += 1

        # Frequency
        advanced_layout.addWidget(QLabel("Frequency (if internal synchronization):"), adv_row, 0)
        w = self.frequency_input = ReturnSpinBox()
        w.setMinimum(1)
        w.setMaximum(250 * 10**6)  # 250 MHz
        w.setSuffix("\xa0Hz")
        w.returnPressed.connect(
            lambda: self.laser.__setattr__("frequency", self.frequency_input.value())
        )
        advanced_layout.addWidget(w, adv_row, 1)
        adv_row += 1

        # Apply button
        w = QPushButton("Apply")
        w.clicked.connect(lambda: self.laser.pdm.apply())
        advanced_layout.addWidget(w, adv_row, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeading)
        adv_row += 1

        self.reload_parameters(all_parameters=True)
        self.laser.parameter_changed.connect(self.reload_parameters)

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
            self.interlock_label.setText("Open" if value == InterlockStatus.OPEN else "Closed")
        elif name == "refresh_interval_ms" and value is not None:
            self.refresh_interval_input.blockSignals(True)
            self.refresh_interval_input.setValue(value)
            self.refresh_interval_input.reset()
            self.refresh_interval_input.blockSignals(False)
        elif name == "temperature":
            self.temperature_label.setText(f"{value:.2f}°C")
        elif name == "sync_source":
            self.sync_source_combobox.blockSignals(True)
            assert isinstance(value, SyncSource)
            match value:
                case SyncSource.EXTERNAL_TTL_LVTTL:
                    self.sync_source_combobox.setCurrentIndex(0)
                case SyncSource.EXTERNAL_LVDS:
                    self.sync_source_combobox.setCurrentIndex(1)
                case SyncSource.INTERNAL:
                    self.sync_source_combobox.setCurrentIndex(2)
            self.sync_source_combobox.blockSignals(False)
        elif name == "delay_line_type":
            self.delay_line_type_combobox.blockSignals(True)
            assert isinstance(value, DelayLineType)
            match value:
                case DelayLineType.NONE:
                    self.delay_line_type_combobox.setCurrentIndex(0)
                case DelayLineType.INTERNAL:
                    self.delay_line_type_combobox.setCurrentIndex(1)
            self.delay_line_type_combobox.blockSignals(False)
        elif name == "pulse_width":
            self.pulse_width_input.blockSignals(True)
            self.pulse_width_input.setValue(value)
            self.pulse_width_input.blockSignals(False)
        elif name == "delay":
            self.delay_input.blockSignals(True)
            self.delay_input.setValue(value)
            self.delay_input.blockSignals(False)
        elif name == "frequency":
            self.frequency_input.blockSignals(True)
            self.frequency_input.setValue(value)
            self.frequency_input.blockSignals(False)

    def reload_parameters(self, param_name: str = "", value: Any = None, all_parameters: bool = False):
        self.sweep_min_input.setValue(self.laser.sweep_min)
        self.sweep_max_input.setValue(self.laser.sweep_max)
        self.sweep_freq_input.setValue(self.laser.sweep_freq)
        if param_name:
            self.refresh_interface(param_name, value)
        else:
            self.refresh_interface("current_percentage", self.laser.current_percentage)
            self.refresh_interface("offset_current", self.laser.offset_current)
            self.refresh_interface("interlock_status", self.laser.interlock_status)
            self.refresh_interface("on_off", self.laser.on_off)
            self.refresh_interface("temperature", self.laser.temperature)
            if all_parameters:
                self.refresh_interface("refresh_interval_ms", self.laser.refresh_interval)
                self.refresh_interface("sync_source", self.laser.sync_source)
                self.refresh_interface("delay_line_type", self.laser.delay_line_type)
                self.refresh_interface("pulse_width", self.laser.pulse_width)
                self.refresh_interface("delay", self.laser.delay)
                self.refresh_interface("frequency", self.laser.frequency)