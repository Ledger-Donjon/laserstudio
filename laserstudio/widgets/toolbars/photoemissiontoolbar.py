from typing import TYPE_CHECKING
from PyQt6.QtWidgets import (
    QToolBar,
    QPushButton,
    QSpinBox,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QLabel,
    QCheckBox,
    QComboBox,
)
from PyQt6.QtCore import Qt
from ...instruments.camera import CameraInstrument

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class PhotoEmissionToolbar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio"):
        self.laser_studio = laser_studio
        assert laser_studio.instruments.camera is not None
        super().__init__("Photoemission", laser_studio)
        self.setObjectName("toolbar-photoemission")  # For settings save and restore
        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea
            | Qt.ToolBarArea.RightToolBarArea
            | Qt.ToolBarArea.BottomToolBarArea
        )
        self.setFloatable(True)
        assert isinstance(laser_studio.instruments.camera, CameraInstrument)
        self.camera = laser_studio.instruments.camera

        w = QWidget()
        self.addWidget(w)
        vbox = QVBoxLayout()
        w.setLayout(vbox)

        # Button to take a black image
        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        hbox.addWidget(QLabel("Reference image"))
        # Select reference image
        self.ref_selection = w = QComboBox()
        w.setEditable(True)
        w.setToolTip("Reference image number")
        w.currentTextChanged.connect(
            lambda v: (
                self.camera.__setattr__("current_reference_image", v),
                self.update_ref_image_controls(),
            )
        )
        hbox.addWidget(w)
        self.takerefbutton = w = QPushButton("Set")
        # Set fixed width to avoid resizing
        w.setFixedWidth(50)
        w.setCheckable(True)
        w.setToolTip("Set/Unset a reference image")
        hbox.addWidget(w)
        w.toggled.connect(
            lambda v: (
                self.camera.take_reference_image(v),
                self.update_ref_image_controls(),
            )
        )

        # Checkbox to activate Image averaging
        w = QWidget()
        vbox.addWidget(w)
        hbox = QHBoxLayout(w)
        w.setLayout(hbox)
        w = QLabel("Image Averaging")
        hbox.addWidget(w)
        w = QSpinBox()
        w.setToolTip("Number of images to average")
        w.setRange(1, 36000)
        w.setValue(self.camera.image_averaging)
        w.valueChanged.connect(lambda v: self.camera.__setattr__("image_averaging", v))
        hbox.addWidget(w)

        # Button to clear all images
        w = QPushButton("Force Clear Average Images")
        w.setToolTip("Clear all averaged images")
        vbox.addWidget(w)
        w.clicked.connect(self.camera.clear_averaged_images)

        # Label to show number of averaged images
        self.averaged_images = w = QLabel()
        # Please keep the (l'), it is an easter egg.
        w.setToolTip("Number of (l')averaged images")
        vbox.addWidget(w)
        self.camera.new_image.connect(
            lambda _: (
                self.averaged_images.setText(
                    f"Images averaged: {self.camera.average_count}"
                ),
            )
        )

        # Checkbox to show negative values
        w = QCheckBox("Show negative activity")
        w.setToolTip("Show negative values")
        w.setCheckable(True)
        w.setChecked(self.camera.show_negative_values)
        w.toggled.connect(lambda x: self.camera.__setattr__("show_negative_values", x))
        vbox.addWidget(w)

        # Checkbox to activate single-mode averaging
        w = QCheckBox("Window mode averaging")
        w.setToolTip(
            "Makes the averaging to be on a rotating window (risk to store too much data)."
            "On non-rotating window mode, the image aquisition stops after the limit being achieved."
            "Trigger a new averaging session with the Clear button."
        )
        w.setCheckable(True)
        w.setChecked(self.camera.windowed_averaging)
        w.toggled.connect(lambda x: self.camera.__setattr__("windowed_averaging", x))
        vbox.addWidget(w)

        vbox.addStretch()

    def update_ref_image_controls(self):
        self.takerefbutton.blockSignals(True)
        self.ref_selection.blockSignals(True)
        self.takerefbutton.setChecked(
            self.camera.reference_image_accumulator is not None
        )
        if self.takerefbutton.isChecked():
            self.takerefbutton.setText("Unset")
        else:
            self.takerefbutton.setText("Set")
        self.ref_selection.setCurrentText(self.camera.current_reference_image)
        self.takerefbutton.blockSignals(False)
        self.ref_selection.blockSignals(False)
