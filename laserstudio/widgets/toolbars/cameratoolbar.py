from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QToolBar,
    QPushButton,
    QDialog,
    QWidget,
    QGridLayout,
    QSlider,
    QLabel,
    QDoubleSpinBox,
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
        self.laser_studio = laser_studio
        assert laser_studio.instruments.camera is not None
        self.camera = laser_studio.instruments.camera
        super().__init__("Camera parameters", laser_studio)
        self.setObjectName("toolbar-camera")  # For settings save and restore
        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea
            | Qt.ToolBarArea.RightToolBarArea
            | Qt.ToolBarArea.BottomToolBarArea
        )
        self.setFloatable(True)

        w = QWidget()
        self.addWidget(w)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        w.setLayout(grid)

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
        w.setIconSize(QSize(16, 16))
        w.toggled.connect(
            lambda b: laser_studio.viewer.stage_sight.__setattr__("show_image", b)
        )
        grid.addWidget(w, 1, 1)

        # Distortion wizard button
        w = QPushButton("Distortion Wizard")
        self.camera_distortion_wizard = CameraDistortionWizard(laser_studio, self)
        w.clicked.connect(lambda: self.camera_distortion_wizard.show())
        grid.addWidget(w, 2, 1)

        # Probes wizard button
        self.probes_distortion_wizard = ProbesPositionWizard(laser_studio, self)
        w = QPushButton("Probes/Spots Wizard")
        w.clicked.connect(lambda: (self.probes_distortion_wizard.show()))
        grid.addWidget(w, 2, 2)
        w.setHidden(
            len(laser_studio.instruments.probes) + len(laser_studio.instruments.lasers)
            == 0
        )

        # Second representation of the camera image
        stage_sight = StageSight(None, self.camera)
        w = StageSightViewer(stage_sight)
        w.setHidden(True)
        grid.addWidget(w, 3, 1, 1, 2)

        # Refresh interval
        w = QWidget()
        grid.addWidget(QLabel("Refresh interval:"), 3, 1)
        self.refresh_interval = w = ReturnSpinBox()
        w.setSuffix("\xa0ms")
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
        grid.addWidget(w, 3, 2)

        if self.camera.shutter is not None:
            w = QPushButton("Shutter")
            w.setCheckable(True)
            w.setChecked(self.camera.shutter.open)
            w.clicked.connect(lambda b: self.camera.shutter.__setattr__("open", b))
            icon = QIcon()
            icon.addPixmap(
                QPixmap(colored_image(":/icons/fontawesome-free/eye-solid.svg")),
                QIcon.Mode.Normal,
                QIcon.State.On,
            )
            icon.addPixmap(
                QPixmap(colored_image(":/icons/fontawesome-free/eye-slash-solid.svg")),
                QIcon.Mode.Normal,
                QIcon.State.Off,
            )
            w.setIcon(icon)
            # self.addWidget(w)
            grid.addWidget(w, 4, 1, 1, 2)

        # Add stretch of last row
        grid.setRowStretch(5, 1)

        self.image_dialog = QDialog()
        self.image_dialog.setWindowTitle("Image Adjustment")
        self.image_dialog.setObjectName("image-adjustment")

        w = QPushButton()
        w.setToolTip(self.image_dialog.windowTitle())
        w.setIcon(QIcon(colored_image(":/icons/fontawesome-free/sliders-solid.svg")))
        w.clicked.connect(lambda: self.image_dialog.show())
        grid.addWidget(w, 1, 2)

        grid = QGridLayout()
        # Image adjustment dialog (for USB camera)
        i = 0
        if type(self.camera) is CameraUSBInstrument:
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

        grid.addWidget(QLabel("Opacity:"), i + 1, 0)
        w = self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.valueChanged.connect(
            lambda a: laser_studio.viewer.stage_sight.image.setOpacity(
                a / self.opacity_slider.maximum()
            )
            if laser_studio.viewer.stage_sight is not None
            else ()
        )
        w.setMinimum(0)
        w.setMaximum(100)
        w.setValue(100)
        grid.addWidget(w, i + 1, 1)

        # Image levels adjustment
        # Add a slider to set the black level
        grid.addWidget(QLabel("Black Level:"), i + 2, 0)
        self.black_level_slider = QSlider(Qt.Orientation.Horizontal)
        self.black_level_slider.setMinimum(0)
        self.black_level_slider.setMaximum(255)
        self.black_level_slider.setValue(int(self.camera.black_level * 255))
        self.black_level_slider.valueChanged.connect(self.update_levels)
        grid.addWidget(self.black_level_slider, i + 2, 1)

        # Add a double spinbox to set the black level
        self.black_level_sb = QDoubleSpinBox()
        self.black_level_sb.setRange(0, 100)
        self.black_level_sb.setDecimals(2)
        self.black_level_sb.setValue(self.camera.black_level * 100)
        self.black_level_sb.valueChanged.connect(
            lambda x: self.update_levels(black=x / 100)
        )
        grid.addWidget(self.black_level_sb, i + 2, 2)

        # Add a slider to set the white level
        grid.addWidget(QLabel("White Level:"), i + 3, 0)
        self.white_level_slider = QSlider(Qt.Orientation.Horizontal)
        self.white_level_slider.setMinimum(0)
        self.white_level_slider.setMaximum(255)
        self.white_level_slider.setValue(int(self.camera.white_level * 255))
        self.white_level_slider.valueChanged.connect(self.update_levels)
        grid.addWidget(self.white_level_slider, i + 3, 1)

        # Add a double spinbox to set the white level
        self.white_level_sb = QDoubleSpinBox()
        self.white_level_sb.setRange(0, 100)
        self.white_level_sb.setDecimals(2)
        self.white_level_sb.setValue(self.camera.white_level * 100)
        self.white_level_sb.valueChanged.connect(
            lambda x: self.update_levels(white=x / 100)
        )
        grid.addWidget(self.white_level_sb, i + 3, 2)

        self.image_dialog.setLayout(grid)
        self.image_dialog.setModal(False)
        self.image_dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)

    def update_levels(self, black=None, white=None):
        if black is None:
            black = self.black_level_slider.value() / self.black_level_slider.maximum()
        if white is None:
            white = self.white_level_slider.value() / self.white_level_slider.maximum()

        self.black_level_slider.blockSignals(True)
        self.black_level_sb.blockSignals(True)
        self.white_level_slider.blockSignals(True)
        self.white_level_sb.blockSignals(True)

        self.black_level_sb.setValue(black * 100)
        self.white_level_sb.setValue(white * 100)
        self.black_level_slider.setValue(int(black * 255))
        self.white_level_slider.setValue(int(white * 255))

        self.black_level_slider.blockSignals(False)
        self.black_level_sb.blockSignals(False)
        self.white_level_slider.blockSignals(False)
        self.white_level_sb.blockSignals(False)

        self.camera.black_level = black
        self.camera.white_level = white
