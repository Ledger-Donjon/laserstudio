from __future__ import annotations

from typing import TYPE_CHECKING
from ...instruments.camera_raptor import (
    CameraRaptorInstrument,
    RaptorCameraControlReg0,
    RaptorCameraControlReg1,
)
from .cameradockwidget import CameraDockWidget, fill_objective_combobox
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QCheckBox,
    QLabel,
    QDoubleSpinBox,
    QGridLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class CameraRaptorDockWidget(CameraDockWidget):
    def __init__(self, laser_studio: LaserStudio):
        assert isinstance(laser_studio.instruments.camera, CameraRaptorInstrument)

        super().__init__(laser_studio)

        self.setObjectName("toolbar-camera-raptor")  # For settings save and restore
        self.camera = laser_studio.instruments.camera

        self.setWindowTitle("Raptor Camera Parameters")

        if self.camera.label:
            self.setWindowTitle(self.windowTitle() + " - " + self.camera.label)

        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
        )

        parentwidget = self.widget()
        assert parentwidget is not None
        grid = parentwidget.layout()
        assert isinstance(grid, QGridLayout)

        col = grid.columnCount()
        row = grid.rowCount()

        vbox = QVBoxLayout()
        grid.addLayout(vbox, 0, col, row, 1)
        col += 1

        # Button to set the Gain Mode
        w = QCheckBox("High Gain")
        w.setToolTip("Get the camera to use high gain mode")
        w.setChecked(self.camera.get_high_gain_enabled())
        w.toggled.connect(self.camera.set_high_gain_enabled)
        vbox.addWidget(w)

        reg_0 = self.camera.get_control_reg_0()
        # Checkbox to activate ALC
        w = QCheckBox("ALC")
        w.setToolTip("Get the camera to use ALC mode")
        w.setChecked(reg_0.__contains__(RaptorCameraControlReg0.ALC_ENABLED))
        w.toggled.connect(self.camera.set_alc_enabled)
        vbox.addWidget(w)

        reg_1 = self.camera.get_control_reg_1()
        # Checkbox to activate AGMC
        w = QCheckBox("AGMC")
        w.setToolTip("Enable the camera's Automatic Gain Mode Control")
        w.setChecked(reg_1.__contains__(RaptorCameraControlReg1.AGMC_ENABLED))
        w.toggled.connect(self.camera.set_agmc_enabled)
        vbox.addWidget(w)
        vbox.addStretch()

        vbox = QVBoxLayout()
        grid.addLayout(vbox, 0, col, row, 1)
        col += 1

        # Set the exposure time
        self.exposure_time_sb = w_sb = QDoubleSpinBox()
        w_sb.setToolTip("Set the camera's exposure time")
        w_sb.setRange(0, 10000)
        w_sb.setSuffix(" ms")
        w_sb.setSingleStep(0.1)
        w_sb.setValue(self.camera.get_exposure_time_ms())
        w_sb.valueChanged.connect(self.camera.set_exposure_time_ms)
        vbox.addWidget(w)

        # Set the gain
        self.gain_sb = w_sb = QDoubleSpinBox()
        w_sb.setToolTip("Set the camera's gain (dB)")
        w_sb.setRange(0, 48)
        w_sb.setSuffix(" dB")
        w_sb.setSingleStep(0.1)
        w_sb.setValue(self.camera.get_digital_gain_db())
        w_sb.valueChanged.connect(self.camera.set_digital_gain_db)
        vbox.addWidget(w)

        w_cb = self.obj_combobox
        fill_objective_combobox(w_cb, self.camera)

        # Show last image number
        self.frame_no_label = w_l = QLabel(f"{self.camera.last_frame_number}")
        w_l.setToolTip("The last image number")
        vbox.addWidget(w)

        vbox.addStretch()

        vbox = QVBoxLayout()
        grid.addLayout(vbox, 0, col, row, 1)
        col += 1

        # Checkbox to activate the FAN
        w = QCheckBox("Fan")
        w.setToolTip("Get the camera to activate the fan")
        w.setCheckable(True)
        w.setChecked(reg_0.__contains__(RaptorCameraControlReg0.FAN_ENABLED))
        w.toggled.connect(self.camera.set_fan_enabled)
        vbox.addWidget(w)

        w = QCheckBox("Fan 2")
        w.setToolTip("Get the camera to activate the fan")
        w.setCheckable(True)
        w.setChecked(reg_1.__contains__(RaptorCameraControlReg1.FAN_ENABLED))
        w.toggled.connect(self.camera.set_fan2_enabled)
        vbox.addWidget(w)
        w.setHidden(True)

        # Checkbox to activate TEC
        w = QCheckBox("TEC")
        w.setToolTip("Enable the camera's TEC")
        w.setCheckable(True)
        w.setChecked(reg_0.__contains__(RaptorCameraControlReg0.TEC_ENABLED))
        w.toggled.connect(self.camera.set_tec_enabled)
        vbox.addWidget(w)

        # Label to show the temperature
        self.temp_label = w_l = QLabel()
        w_l.setToolTip("The camera's temperature")
        w_l.setFixedWidth(150)
        vbox.addWidget(w_l)
        self.camera.temperature_changed.connect(
            lambda t: self.temp_label.setText(f"Temperature: {t:.2f}°C")
        )

        self.temperature_setpoint = w_sb = QDoubleSpinBox()
        w_sb.setRange(-20, 20)
        w_sb.setSuffix("°C")
        w_sb.setSingleStep(1)
        w_sb.setValue(self.camera.get_tec_temperature_setpoint())
        w_sb.valueChanged.connect(self.camera.set_tec_temperature_setpoint)
        vbox.addWidget(w_sb)
        vbox.addStretch()

        # At each new image:
        # Refresh the image number, temperature, exposure time and gain
        self.camera.new_image.connect(lambda _: self.on_new_image())

    def on_new_image(self, _: QImage | None = None) -> None:
        if isinstance(self.camera, CameraRaptorInstrument):
            temperature = self.camera.get_sensor_temperature()
            self.temp_label.setText(f"Temperature: {temperature:.2f}°C")
            self.frame_no_label.setText(f"{self.camera.last_frame_number}")
            self.exposure_time_sb.setValue(self.camera.get_exposure_time_ms())
            self.gain_sb.setValue(self.camera.get_digital_gain())
