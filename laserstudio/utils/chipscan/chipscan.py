from PyQt6.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QWidget,
    QPushButton,
    QButtonGroup,
)
from PyQt6.QtGui import QShortcut, QImage, QPixmap
from PyQt6.QtCore import Qt

from ...instruments.instruments import (
    Instruments,
    CameraNITInstrument,
    CameraRaptorInstrument,
)
from ...widgets.stagesight import StageSight, StageSightViewer
from ...widgets.toolbars import (
    CameraNITToolBar,
    CameraRaptorToolBar,
    StageToolBar,
    CameraImageAdjustmentToolBar,
    LightToolBar,
    FocusToolBar,
)


class ScanConfig:
    def __init__(self, config):
        """
        :param config: YAML config object.
        """
        self.margin_x = config.get("margin-x")
        self.margin_y = config.get("margin-y")
        self.overlap = config.get("overlap")


class ChipScan(QMainWindow):
    def __init__(self, config: dict):
        """
        Laser Studio main window.

        :param config: Optional configuration dictionary.
        """
        super().__init__()
        self.config = config
        self.instruments = Instruments(config)
        self.scan_config = ScanConfig(config)

        stage = self.instruments.stage
        camera = self.instruments.camera

        assert stage is not None, "No stage found in config"
        assert camera is not None, "No camera found in config"

        self.stage = stage
        self.camera = camera

        self.viewer = StageSightViewer(StageSight(stage, camera))
        self.viewer_buttons_group = QButtonGroup(self)
        if self.camera:
            self.addToolBar(CameraImageAdjustmentToolBar(self))
        if isinstance(self.camera, CameraNITInstrument):
            self.addToolBar(CameraNITToolBar(self))
        if isinstance(self.camera, CameraRaptorInstrument):
            self.addToolBar(toolbar := CameraRaptorToolBar(self))
        toolbar = StageToolBar(self)
        self.addToolBar(toolbar)
        if light := self.instruments.light:
            self.addToolBar(LightToolBar(light))
        if focus_helper := self.instruments.focus_helper:
            self.addToolBar(FocusToolBar(stage, camera, focus_helper))

        # Create shortcuts
        shortcut = QShortcut(Qt.Key.Key_PageUp, self)
        shortcut.activated.connect(lambda: self.move_z(1.0))
        shortcut = QShortcut(Qt.Key.Key_PageDown, self)
        shortcut.activated.connect(lambda: self.move_z(-1.0))
        shortcut = QShortcut(Qt.Key.Key_Control + Qt.Key.Key_PageUp, self)
        shortcut.activated.connect(lambda: self.move_z(10.0))
        shortcut = QShortcut(Qt.Key.Key_Control + Qt.Key.Key_PageDown, self)
        shortcut.activated.connect(lambda: self.move_z(-10.0))

        self.setWindowTitle("Chip-Scan")
        w = QWidget()
        vbox = QVBoxLayout()
        w.setLayout(vbox)

        self.setCentralWidget(w)
        self.resize(800, 600)

        hbox = QHBoxLayout()
        hbox.setSpacing(0)
        vbox.addLayout(hbox)

        w = self.image_label = QLabel()  # StageSightViewer(stage_sight)
        hbox.addStretch()
        hbox.addWidget(w)
        w = self.image_label_right = QLabel()
        w.hide()
        hbox.addWidget(w)
        hbox.addStretch()

        # Layout for camera settings
        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        w = QPushButton("Rot")
        w.clicked.connect(self.camera_rotation_test)
        hbox.addWidget(w)

        self.camera.new_image.connect(self.refresh)

    def move_z(self, direction: float):
        """
        Called with keyboard page up and page down shortcuts. Move the stage
        vertically for focusing.

        :param direction: 1 to move up, -1 to move down.
        """
        assert direction in (-1.0, -10.0, 1.0, 10.0)
        pos = self.stage.position
        pos.z += direction * -1
        self.stage.position = pos
        # self.stage.enable_joystick()

    def refresh(self, image: QImage):
        """Update the camera image in the UI."""
        self.image_label.setPixmap(QPixmap.fromImage(image))

    def camera_rotation_test(self):
        """Takes a second image to visualize camera angle."""
        self.image_label_right.setPixmap(self.image_label.pixmap())
        self.image_label_right.show()
