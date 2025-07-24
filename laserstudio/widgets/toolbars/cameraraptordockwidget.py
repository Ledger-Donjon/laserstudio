from typing import TYPE_CHECKING
from ...instruments.camera_raptor import (
    CameraRaptorInstrument,
    RaptorCameraControlReg0,
    RaptorCameraControlReg1,
)
from .cameradockwidget import CameraDockWidget
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QComboBox,
    QGridLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from ...utils import util

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class CameraRaptorDockWidget(CameraDockWidget):
    def __init__(self, laser_studio: "LaserStudio"):
        assert isinstance(laser_studio.instruments.camera, CameraRaptorInstrument)

        super().__init__(laser_studio)
        self.setWindowTitle("Raptor Camera parameters")
        self.setObjectName("toolbar-camera-raptor")  # For settings save and restore
        self.camera = laser_studio.instruments.camera

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
        w.setCheckable(True)
        w.setChecked(self.camera.get_high_gain_enabled())
        w.toggled.connect(self.camera.set_high_gain_enabled)
        vbox.addWidget(w)

        reg_0 = self.camera.get_control_reg_0()
        # Checkbox to activate ALC
        w = QCheckBox("ALC")
        w.setToolTip("Get the camera to use ALC mode")
        w.setCheckable(True)
        w.setChecked(reg_0.__contains__(RaptorCameraControlReg0.ALC_ENABLED))
        w.toggled.connect(self.camera.set_alc_enabled)
        vbox.addWidget(w)

        reg_1 = self.camera.get_control_reg_1()
        # Checkbox to activate AGMC
        w = QCheckBox("AGMC")
        w.setToolTip("Enable the camera's Automatic Gain Mode Control")
        w.setCheckable(True)
        w.setChecked(reg_1.__contains__(RaptorCameraControlReg1.AGMC_ENABLED))
        w.toggled.connect(self.camera.set_agmc_enabled)
        vbox.addWidget(w)
        vbox.addStretch()

        vbox = QVBoxLayout()
        grid.addLayout(vbox, 0, col, row, 1)
        # Set the exposure time
        self.exposure_time_sb = w = QDoubleSpinBox()
        w.setToolTip("Set the camera's exposure time")
        w.setRange(0, 10000)
        w.setSuffix(" ms")
        w.setSingleStep(0.1)
        w.setValue(self.camera.get_exposure_time_ms())
        w.valueChanged.connect(self.camera.set_exposure_time_ms)
        vbox.addWidget(w)

        # Set the gain
        self.gain_sb = w = QDoubleSpinBox()
        w.setToolTip("Set the camera's gain (dB)")
        w.setRange(0, 48)
        w.setSuffix(" dB")
        w.setSingleStep(0.1)
        w.setValue(self.camera.get_digital_gain_db())
        w.valueChanged.connect(self.camera.set_digital_gain_db)
        vbox.addWidget(w)

        # Magnification selector.
        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        hbox.addWidget(QLabel("Objective:"))
        w = self.mag_combobox = QComboBox()
        for x in [10, 20]:
            icon = QIcon(util.resource_path(f":/icons/obj-{x}x.png"))
            w.addItem(icon, f"{x} X")
            if x == self.camera.objective:
                w.setCurrentIndex(w.count() - 1)
        w.setStyleSheet("QListView::item {height:24px;}")
        w.currentIndexChanged.connect(self.mag_changed)
        hbox.addWidget(w)

        # Show last image number
        self.frame_no_label = w = QLabel(f"{self.camera.last_frame_number}")
        w.setToolTip("The last image number")
        vbox.addWidget(w)

        vbox.addStretch()

        vbox = QVBoxLayout()
        hbox.addLayout(vbox)

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
        self.temp_label = w = QLabel()
        w.setToolTip("The camera's temperature")
        w.setFixedWidth(150)
        vbox.addWidget(w)
        self.camera.temperature_changed.connect(
            lambda t: self.temp_label.setText(f"Temperature: {t:.2f}°C")
        )

        self.temperature_setpoint = QDoubleSpinBox()
        self.temperature_setpoint.setRange(-20, 20)
        self.temperature_setpoint.setSuffix("°C")
        self.temperature_setpoint.setSingleStep(1)
        self.temperature_setpoint.setValue(self.camera.get_tec_temperature_setpoint())
        self.temperature_setpoint.valueChanged.connect(
            self.camera.set_tec_temperature_setpoint
        )
        vbox.addWidget(self.temperature_setpoint)
        vbox.addStretch()

        # At each new image:
        # Refresh the image number, temperature, exposure time and gain
        self.camera.new_image.connect(
            lambda _: (
                self.camera.get_sensor_temperature(),
                self.frame_no_label.setText(f"{self.camera.last_frame_number}"),
                self.exposure_time_sb.setValue(self.camera.get_exposure_time_ms()),
                self.gain_sb.setValue(self.camera.get_digital_gain_db()),
            )
        )

    def mag_changed(self):
        """
        Called when the magnification is changed in the UI.
        """
        self.camera.select_objective(float(self.mag_combobox.currentText().split()[0]))
        assert self.laser_studio.viewer.stage_sight is not None
        self.laser_studio.viewer.stage_sight.update_size()
