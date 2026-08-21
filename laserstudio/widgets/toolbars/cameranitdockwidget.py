from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
import pickle
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDockWidget,
    QPushButton,
    QComboBox,
    QWidget,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QMessageBox,
)
from ..coloredbutton import ColoredPushButton
from ..return_line_edit import ReturnDoubleSpinBox, ReturnSpinBox
from ...instruments.camera_nit import CameraNITInstrument
from .cameradockwidget import fill_objective_combobox, _objective_combobox_index

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio
from PyQt6.QtCore import QTimer


class CameraNITDockWidget(QDockWidget):
    def __init__(self, laser_studio: LaserStudio):
        """
        Initialize the camera NIT toolbar.

        :param laser_studio: The laser studio instance.
        """
        assert isinstance(laser_studio.instruments.camera, CameraNITInstrument)
        self.camera = laser_studio.instruments.camera
        self.laser_studio = laser_studio

        super().__init__("NIT Camera Parameters", laser_studio)

        if self.camera.label is not None:
            self.setWindowTitle(self.windowTitle() + " - " + self.camera.label)

        self.setObjectName("toolbar-camera-nit")  # For settings save and restore
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
        )

        w = QWidget()
        self.setWidget(w)
        vbox = QVBoxLayout()
        w.setLayout(vbox)

        # Gain management
        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        hbox.addWidget(QLabel("Gain:"))
        w = self.hist_low_input = ReturnDoubleSpinBox()
        w.setMinimum(0)
        w.setMaximum(0xFFFF)
        w.returnPressed2.connect(self.gain_changed)
        hbox.addWidget(w)
        w = self.hist_high_input = ReturnDoubleSpinBox()
        w.setMinimum(0)
        w.setMaximum(0xFFFF)
        w.returnPressed2.connect(self.gain_changed)
        hbox.addWidget(w)
        # Button to trigger the NIT camera gain
        # Checkbox to activate/deactivate the timer
        self.agc_button = w = ColoredPushButton()
        w.setText("AGC")
        w.setToolTip("Auto gain control (every 1 second)")
        w.setCheckable(True)
        # w.setChecked(True)
        w.clicked.connect(self.agc_button_changed)
        hbox.addWidget(w)
        # Timer to trigger gain autoset every 1 seconds
        self.timer = QTimer()
        self.timer.timeout.connect(self.gain_autoset)
        self.timer.setInterval(1000)  # 1 second interval
        self.agc_button_changed(self.agc_button.isChecked())

        # Averaging management
        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        hbox.addWidget(QLabel("Averaging:"))
        w = self.averaging = ReturnSpinBox()
        w.setMinimum(1)
        w.setMaximum(255)
        w.reset()
        w.returnPressed2.connect(self.averaging_changed)
        hbox.addWidget(w)

        # Magnification selector.
        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        hbox.addWidget(QLabel("Objective:"))
        w = self.obj_combobox = QComboBox()
        fill_objective_combobox(w, self.camera)
        w.setStyleSheet("QListView::item {height:24px;}")
        w.currentIndexChanged.connect(self.obj_changed)
        hbox.addWidget(w)

        # Shading correction
        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        w = QPushButton("Shade")
        w.setToolTip("Set current image as shading correction")
        w.clicked.connect(self.camera.shade_correct)
        hbox.addWidget(w)

        w = QPushButton("Clear")
        w.setToolTip("Clear shading correction")
        w.clicked.connect(self.camera.clear_shade_correction)
        hbox.addWidget(w)

        w = QPushButton("Save")
        w.setToolTip("Save shading correction")
        w.clicked.connect(self.shade_save)
        hbox.addWidget(w)

        w = QPushButton("Load")
        w.setToolTip("Load shading correction")
        w.clicked.connect(self.shade_load)
        hbox.addWidget(w)

        # Add stretch of last row
        vbox.addStretch()

        self.camera.parameter_changed.connect(self.camera_parameter_changed)
        logging.getLogger("laserstudio").info("Camera NIT DockWidget initialized")

    def camera_parameter_changed(self, parameter: str, value: Any):
        if parameter == "objective" and isinstance(value, float):
            self.obj_combobox.blockSignals(True)
            index = _objective_combobox_index(self.obj_combobox, value)
            if index != -1:
                self.obj_combobox.setCurrentIndex(index)
            else:
                logging.getLogger("laserstudio").warning(
                    f"Received unsupported objective value from camera: {value:g} X. "
                    "The combobox will not reflect the actual value."
                )
            self.obj_combobox.blockSignals(False)

    def gain_changed(self):
        """
        Called when histogram gain bound is changed in the UI.
        """
        low = self.hist_low_input.value()
        high = self.hist_high_input.value()
        if low > high:
            self.hist_low_input.setValue(high)
            self.hist_high_input.setValue(low)
        try:
            self.camera.gain = (
                float(self.hist_low_input.value()),
                float(self.hist_high_input.value()),
            )
        except ValueError:
            pass

    def gain_autoset(self):
        """
        Called when the auto gain is triggered by the timer.
        """
        low, high = self.camera.gain_autoset()
        self.hist_low_input.setValue(low)
        self.hist_high_input.setValue(high)
        self.hist_low_input.reset()
        self.hist_high_input.reset()

    def averaging_changed(self):
        """
        Called when the averaging value is changed in the UI.
        """
        try:
            self.camera.averaging = self.averaging.value()
        except ValueError:
            pass

    def obj_changed(self):
        """
        Called when the magnification is changed in the UI.
        """
        logging.getLogger("laserstudio").debug(
            f"Objective changed to {self.obj_combobox.currentText()}"
        )
        data = self.obj_combobox.currentData()
        if isinstance(data, (float, int)):
            self.camera.select_objective(float(data))
        else:
            self.camera.select_objective(
                float(self.obj_combobox.currentText().split()[0])
            )
        assert self.laser_studio.viewer.stage_sight is not None
        self.laser_studio.viewer.stage_sight.update_size()

    def shade_save(self):
        """
        Save shading correction to file.
        """
        data = self.camera.shade_correction
        with open(f"shade-{self.camera.objective:.0f}x.pickle", "wb") as f:
            pickle.dump(data, f)

    def shade_load(self):
        """
        Load shading correction from file.
        """
        try:
            with open(f"shade-{self.camera.objective:.0f}x.pickle", "rb") as f:
                self.camera.shade_correction = pickle.load(f)
        except FileNotFoundError:
            QMessageBox().critical(None, "Error", "Shading correction file not found.")

    def agc_button_changed(self, state: bool):
        """
        Called when AGC button is toggled.
        Enables or disables Automatic Gain Correction.

        :param state: True when button is checked, which enables AGC. False otherwise.
        """
        if state:
            # Apply gain correction immediately, don't wait 1 second
            # for the timer to timeout.
            self.gain_autoset()
            # Re-enabled timer
            self.timer.start()
        else:
            self.timer.stop()
