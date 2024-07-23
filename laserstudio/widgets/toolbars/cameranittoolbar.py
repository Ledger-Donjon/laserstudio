from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QToolBar,
    QPushButton,
    QComboBox,
    QWidget,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QMessageBox,
)
from ..return_line_edit import ReturnSpinBox
from ...instruments.camera_nit import CameraNITInstrument
from ...utils import util
import pickle

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio
from PyQt6.QtCore import QTimer


class CameraNITToolBar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio"):
        assert isinstance(laser_studio.instruments.camera, CameraNITInstrument)
        self.camera = laser_studio.instruments.camera
        self.laser_studio = laser_studio

        super().__init__("NIT Camera parameters", laser_studio)
        self.setObjectName("toolbar-camera-nit")  # For settings save and restore
        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea
            | Qt.ToolBarArea.RightToolBarArea
            | Qt.ToolBarArea.BottomToolBarArea
        )
        self.setFloatable(True)

        w = QWidget()
        self.addWidget(w)
        vbox = QVBoxLayout()
        w.setLayout(vbox)

        # Gain management
        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        hbox.addWidget(QLabel("Gain:"))
        w = self.hist_low_input = ReturnSpinBox()
        w.setMinimum(0)
        w.setMaximum(0xFFFF)
        w.returnPressed.connect(self.gain_changed)
        hbox.addWidget(w)
        w = self.hist_high_input = ReturnSpinBox()
        w.setMinimum(0)
        w.setMaximum(0xFFFF)
        w.returnPressed.connect(self.gain_changed)
        hbox.addWidget(w)
        # Button to trigger the NIT camera gain
        # Checkbox to activate/deactivate the timer
        w = QPushButton("AGC")
        w.setToolTip("Auto gain control (every 1 second)")
        w.setCheckable(True)
        w.setChecked(True)
        w.clicked.connect(
            lambda state: self.timer.setInterval(1000) if state else self.timer.stop()
        )
        hbox.addWidget(w)
        # Timer to trigger gain autoset every 1 seconds
        self.timer = QTimer()
        self.timer.timeout.connect(self.gain_autoset)
        self.timer.start(1000)  # 1 seconds interval

        # Averaging management
        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        hbox.addWidget(QLabel("Averaging:"))
        w = self.averaging = ReturnSpinBox()
        w.setMinimum(1)
        w.setMaximum(255)
        w.reset()
        w.returnPressed.connect(self.averaging_changed)
        hbox.addWidget(w)

        # Magnification selector.
        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        hbox.addWidget(QLabel("Objective:"))
        w = self.mag_combobox = QComboBox()
        for x in [5, 10, 20, 50]:
            icon = QIcon(util.resource_path(f":/icons/obj-{x}x.png"))
            w.addItem(icon, f"{x} X")
            if x == self.camera.objective:
                w.setCurrentIndex(w.count() - 1)
        w.setStyleSheet("QListView::item {height:24px;}")
        w.currentIndexChanged.connect(self.mag_changed)
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
        Called when the auto gain button is clicked.
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

    def mag_changed(self):
        """
        Called when the magnification is changed in the UI.
        """
        self.camera.select_objective(float(self.mag_combobox.currentText().split()[0]))
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
