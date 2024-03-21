from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QToolBar,
    QPushButton,
    QDialog,
    QWidget,
    QSizePolicy,
    QGridLayout,
    QSlider,
    QLabel,
)
from ...utils.util import colored_image
from ..stagesight import StageSightViewer, StageSight
from ..camerawizards import CameraDistortionWizard, ProbesPositionWizard
from ..return_line_edit import ReturnSpinBox
from ...instruments.camera_usb import CameraUSBInstrument

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class CameraToolbar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio"):
        assert laser_studio.instruments.camera is not None
        self.camera = laser_studio.instruments.camera
        super().__init__("Camera parameters", laser_studio)
        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
        )
        self.setFloatable(True)

        # Button to toggle off or on the camera image presentation in main viewer
        w = QPushButton(self)
        w.setToolTip("Show/Hide Image")
        w.setCheckable(True)
        w.setChecked(True)
        icon = QIcon()
        icon.addPixmap(
            colored_image(":/icons/fontawesome-free/video-solid.svg"),
            QIcon.Mode.Normal,
            QIcon.State.On,
        )
        icon.addPixmap(
            colored_image(":/icons/fontawesome-free/video-slash-solid.svg"),
            QIcon.Mode.Normal,
            QIcon.State.Off,
        )
        w.setIcon(icon)
        w.setIconSize(QSize(24, 24))
        w.toggled.connect(
            lambda b: laser_studio.viewer.stage_sight.__setattr__("show_image", b)
        )
        self.addWidget(w)

        w = QPushButton(self)
        w.setText("Distortion Wizard")
        self.camera_distortion_wizard = CameraDistortionWizard(laser_studio, self)
        w.clicked.connect(lambda: self.camera_distortion_wizard.show())
        self.addWidget(w)

        self.probes_distortion_wizard = ProbesPositionWizard(laser_studio, self)
        w = QPushButton(self)
        w.setText("Probes/Spots Position Wizard")
        w.clicked.connect(lambda: (self.probes_distortion_wizard.show()))
        self.addWidget(w)
        w.setHidden(
            len(laser_studio.instruments.probes) + len(laser_studio.instruments.lasers)
            == 0
        )

        # Second representation of the camera image
        stage_sight = StageSight(None, self.camera)
        w = StageSightViewer(stage_sight)
        w.setHidden(True)
        self.addWidget(w)

        # Refresh interval
        self.refresh_interval = w = ReturnSpinBox()
        w.setSuffix("ms")
        w.setMinimum(20)
        w.setMaximum(10000)
        w.setSingleStep(10)
        w.setValue(self.camera.refresh_interval)
        w.reset()
        w.setToolTip("Refresh interval")
        w.returnPressed.connect(
            lambda: self.camera.__setattr__(
                "refresh_interval", self.refresh_interval.value()
            )
        )
        self.addWidget(w)

        # Image adjustment dialog (for USB camera)
        if isinstance(self.camera, CameraUSBInstrument):
            self.image_dialog = QDialog()
            self.image_dialog.setWindowTitle("Image Adjustment")
            sliders = QWidget(self.image_dialog)
            sliders.setSizePolicy(
                QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding
            )
            grid = QGridLayout()
            sliders.setLayout(grid)
            for i, (att, minimum, maximum) in enumerate(
                [
                    ("brightness", 0, 255),
                    ("contrast", 0, 31),
                    ("saturation", 0, 31),
                    ("hue", -180, 180),
                    ("gamma", 0, 127),
                    ("sharpness", 0, 15),
                ]
            ):
                grid.addWidget(QLabel(f"{att.capitalize()}:"), i, 0)
                w = QSlider(Qt.Orientation.Horizontal)
                w.setMinimum(minimum)
                w.setMaximum(maximum)
                w.setValue(int(getattr(self.camera, att)))
                w.valueChanged.connect(
                    lambda x, _att=att: setattr(self.camera, _att, x)
                )
                grid.addWidget(w, i, 1)
            w = QPushButton(self.image_dialog.windowTitle())
            w.clicked.connect(lambda: self.image_dialog.exec())
            self.addWidget(w)
