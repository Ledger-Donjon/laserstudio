from PyQt6.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QWidget,
    QPushButton,
    QButtonGroup,
    QSizePolicy,
    QCheckBox,
    QApplication,
    QGridLayout,
    QProgressBar,
    QMessageBox,
    QLineEdit,
)
from PyQt6.QtGui import QShortcut, QImage, QPixmap
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from ...instruments.instruments import (
    Instruments,
    CameraNITInstrument,
    CameraRaptorInstrument,
    StageInstrument,
    CameraInstrument,
    FocusInstrument,
)
from ...widgets.stagesight import StageSight, StageSightViewer
from ...widgets.toolbars import (
    CameraNITToolBar,
    CameraRaptorToolBar,
    StageToolBar,
    CameraImageAdjustmentToolBar,
    LightToolBar,
    FocusToolBar,
    PhotoEmissionToolBar,
    MainToolBar
)
from PIL import Image, ImageDraw
from pystages import Vector
import time
from typing import Optional, Any, cast, TYPE_CHECKING
import math
from .scan_file import ScanFile
import os
import yaml

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio

class ScanConfig:
    def __init__(self, config: dict[str, Any]):
        """
        :param config: YAML config object.
        """
        self.margin_x = float(config.get("margin-x", 128.0))
        self.margin_y = float(config.get("margin-y", 102.0))
        self.overlap = float(config.get("overlap", 0.0))


class ScanThread(QThread):
    # Set to True to stop scan
    stop = False

    # Signal emited when scanning progresses
    progressed = pyqtSignal(int, int)

    def __init__(
        self,
        config: ScanConfig,
        camera: CameraInstrument,
        stage: StageInstrument,
        bl: Vector,
        tr: Vector,
        focus: Optional[FocusInstrument],
        chipscan: "ChipScan",
    ):
        """
        Scan thread.

        :param config: Scan configuration.
        :param camera: Camera instrument.
        :param stage: Stage instrument.
        :param bl: Bottom left corner of the scan area.
        :param tr: Top right corner of the scan area.
        :param focus: List of points for autofocus.
        :param mag: Magnification objective.
        :param avg: Number of images to average.
        """
        super().__init__()
        self.config = config
        self.camera = camera
        self.stage = stage
        self.__bl = bl
        self.__tr = tr
        self.focus = focus
        self.__mag = self.camera.objective
        self.__chipscan = chipscan
        # self.__avg = self.camera.averaging_count

        # Get the range coordinates. Make sure the top bottom-left corner is
        # really the bottom-left corner.
        self.__ref_z = (
            focus.autofocus_helper.registered_points[0][2] if focus is not None else 0.0
        )
        self.__x0 = float(min(self.__bl[0], self.__tr[0]))
        self.__x1 = float(max(self.__bl[0], self.__tr[0]))
        self.__y0 = float(min(self.__bl[1], self.__tr[1]))
        self.__y1 = float(max(self.__bl[1], self.__tr[1]))
        self.__dx = self.__x1 - self.__x0
        self.__dy = self.__y1 - self.__y0

        # Calculate the size of 1 pixel.
        pixel_size_x = self.camera.pixel_size_in_um[0] / self.__mag
        pixel_size_y = self.camera.pixel_size_in_um[1] / self.__mag

        # Calculate scanning displacement for each image
        self.__disp_x = pixel_size_x * (
            self.camera.width - self.config.overlap - self.config.margin_x * 2
        )
        self.__disp_y = pixel_size_y * (
            self.camera.height - self.config.overlap - self.config.margin_y * 2
        )

        # Calculate the number of tiles to be scanned.
        self.__num_x = math.ceil(self.__dx / self.__disp_x) + 1
        self.__num_y = math.ceil(self.__dy / self.__disp_y) + 1

    def __tile_pos(self, x: int, y: int):
        """
        :return: Given tile position.

        :param x: Tile abscissa. -1 allowed for backlash compensation.
        :param y: Tile ordinate. -1 allowed for backlash compensation.
        """
        assert x >= -1
        assert y >= -1
        return self.__x0 + self.__disp_x * x, self.__y0 + self.__disp_y * y

    def __move_to_tile(self, x: int, y: int):
        """
        Move stage to tile. Wait for move to be finished.
        :param x: Tile abscissa. -1 allowed for backlash compensation.
        :param y: Tile ordinate. -1 allowed for backlash compensation.
        """
        pos = self.__tile_pos(x, y)
        if self.focus is not None:
            z = self.focus.autofocus_helper.focus(*pos)
            # Calculate focus. Verify it is not a calculation error which
            # goes way too far...
            max_delta_z = 5000
            assert abs(z - self.__ref_z) < max_delta_z, (
                f"Prevent autofocus with a z-change bigger than {max_delta_z} um"
            )
            self.stage.move_to(Vector(pos[0], pos[1], z), wait=True, backlash=True)

    @property
    def num_tiles(self):
        """
        :return: Number of tiles to be scanned.
        """
        return self.__num_x * self.__num_y

    def run(self):
        # Create scanning properties file.
        scan_file = ScanFile()
        scan_file.num_x = self.__num_x
        scan_file.num_y = self.__num_y
        scan_file.img_width = self.camera.width - self.config.margin_x * 2
        scan_file.img_height = self.camera.height - self.config.margin_y * 2
        scan_file.img_overlap = self.config.overlap
        scan_file.file_prefix = self.__chipscan.file_prefix.text()
        os.makedirs("tmp", exist_ok=True)
        scan_file.save(os.path.join("tmp", "scan.yaml"))

        # Backlash compensation over Y axis
        self.__move_to_tile(-1, -1)
        for iy in range(0, self.__num_y):
            # Backlash compensation over X axis
            self.__move_to_tile(-1, iy)
            for ix in range(0, self.__num_x):
                self.progressed.emit(iy * self.__num_x + ix, self.num_tiles)
                if self.stop:
                    return
                self.__move_to_tile(ix, iy)
                if self.stop:
                    return
                # Restart averaging
                self.camera.clear_averaged_images()
                while not self.camera.is_average_valid:
                    time.sleep(0.1)
                # (Re)restart averaging
                self.camera.clear_averaged_images()
                # Wait for averaging to complete
                while not self.camera.is_average_valid:
                    time.sleep(0.1)
                time.sleep(0.1)
                # Capture image
                self.__chipscan._last_image = None
                time.sleep(0.1)
                while self.__chipscan.last_image is None:
                    QApplication.processEvents()
                time.sleep(0.1)
                im = self.__chipscan.last_image.copy()
                box = (
                    self.config.margin_x,
                    self.config.margin_y,
                    self.camera.width - self.config.margin_x,
                    self.camera.height - self.config.margin_y,
                )
                prefix = self.__chipscan.file_prefix.text()
                filename = [f"{ix:03d}", f"{iy:03d}"]
                if prefix:
                    filename = [prefix] + filename
                imcroped = im.crop(box)
                imcroped.save(os.path.join("tmp", "_".join(filename) + ".png"))
                filename.insert(-2, "full")
                im.save(os.path.join("tmp", "_".join(filename) + ".png"))
                del im, imcroped
        # Return to start.
        self.__move_to_tile(0, 0)


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

        selfls = cast('LaserStudio', self) 
        self.addToolBar(MainToolBar(selfls))
        if self.camera:
            self.addToolBar(CameraImageAdjustmentToolBar(selfls))
            self.addToolBar(PhotoEmissionToolBar(selfls))
        if isinstance(self.camera, CameraNITInstrument):
            self.addToolBar(CameraNITToolBar(selfls))
        if isinstance(self.camera, CameraRaptorInstrument):
            self.addToolBar(CameraRaptorToolBar(selfls))
        toolbar = StageToolBar(selfls)
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

        # Cross option
        w = QLabel("Center cross: ")
        w.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        hbox.addWidget(w)
        w = self.center_cross_checkbox = QCheckBox()
        hbox.addWidget(w)
        w = QLabel("Margin: ")
        w.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        hbox.addWidget(w)
        w = self.margin_checkbox = QCheckBox()
        w.setChecked(True)
        hbox.addWidget(w)

        # Chip positioning
        grid = QGridLayout()
        vbox.addLayout(grid)
        positions = (
            ("Upper-left corner", 1, 0),
            ("Lower-right corner", 2, 0),
        )
        self.pos_buttons: list[QPushButton] = []
        for i, (label, row, col) in enumerate(positions):
            grid.addWidget(QLabel(label + ":"), row, col)
            w = QPushButton("Set")
            w.clicked.connect(lambda _, bound_i=i: self.set_pos(bound_i))
            self.pos_buttons.append(w)
            grid.addWidget(w, row, col + 1)

        # Button to start images acquisition
        w = self.acquire_button = QPushButton("Acquire images")
        grid.addWidget(w, 4, 4)
        w.setMinimumWidth(150)
        w.setEnabled(False)
        w.clicked.connect(self.acquire)

        # Button to interrupt images acquisition
        w = self.stop_button = QPushButton("Stop")
        w.hide()
        w.setEnabled(False)
        grid.addWidget(w, 4, 5)

        self.camera.new_image.connect(self.refresh)
        hbox.addWidget(w)
        self.positions: list[Optional[Vector]] = [None] * len(self.pos_buttons)

        self.file_prefix = QLineEdit()
        self.file_prefix.setPlaceholderText("File prefix")
        self.file_prefix.setText("scan")

        w = self.scan_progress_bar = QProgressBar()
        w.hide()
        hbox.addWidget(w)

        self._last_image: Optional[Image.Image] = None

    @property
    def last_image(self):
        """
        :return: Last image captured.
        """
        return self._last_image

    def stop(self):
        """
        Stop the scan thread.
        """
        if self.scan_thread is not None:
            self.scan_thread.stop = True
            self.scan_thread.wait()
            self.scan_thread = None

    def acquire(self):
        """
        Starts images acquisition.
        """
        bl, tr = self.positions[0], self.positions[1]
        assert bl is not None
        assert tr is not None
        t = ScanThread(
            self.scan_config,
            self.camera,
            self.stage,
            bl,
            tr,
            self.instruments.focus_helper,
            self,
        )
        if (
            QMessageBox.question(
                self,
                "Start ?",
                "{0} tiles to be captured. Continue ?".format(t.num_tiles),
            )
            == QMessageBox.StandardButton.Yes
        ):
            # Disable buttons, show progress bar...
            self.acquire_button.setEnabled(False)
            self.scan_progress_bar.show()
            self.scan_progress_bar.setValue(0)
            self.stop_button.show()
            self.acquire_button.hide()
            for button in self.pos_buttons:
                button.setEnabled(False)
            # Start scanning !
            self.scan_thread = t
            t.progressed.connect(self.acquisition_progressed)
            t.finished.connect(self.acquisition_finished)
            t.started.connect(self.acquisition_started)
            t.start()

    def acquisition_started(self):
        """
        Called when acquisition starts. Disable buttons. Show/hide elements.
        """
        self.acquire_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        for button in self.pos_buttons:
            button.setEnabled(False)
        self.scan_progress_bar.setValue(0)
        self.scan_progress_bar.show()
        self.acquire_button.hide()
        self.stop_button.show()

    def acquisition_progressed(self, current: int, total: int):
        """
        Called when a tile has been acquired. Update progress bar.

        :param current: Current tile number.
        :param total: Total number of tiles.
        """
        self.scan_progress_bar.setValue(int(current * 100 / total))

    def acquisition_finished(self):
        self.acquire_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        for button in self.pos_buttons:
            button.setEnabled(True)
        self.scan_progress_bar.setValue(100)
        self.scan_progress_bar.hide()
        self.acquire_button.show()
        self.stop_button.hide()

    def update_acquire_button_enable(self):
        """
        Enable the acquire button if all positions are set.
        """
        self.acquire_button.setEnabled(all(pos is not None for pos in self.positions))

    def set_pos(self, index: int):
        """
        Called when a button to define a position parameter has been clicked.
        Save the value, focus to next button step and refresh UI.

        :param index: Position index.
        """
        pos = self.stage.position
        self.positions[index] = Vector(pos.x, pos.y, pos.z)
        button = self.pos_buttons[index]
        if index < 2:
            # Corner points, no need to display Z
            button.setText("{0:.0f}, {1:.0f}".format(pos[0], pos[1]))
        else:
            # Focus points
            button.setText("{0:.0f}, {1:.0f}, {2:.0f}".format(pos[0], pos[1], pos[2]))
        self.update_acquire_button_enable()

        if index + 1 < len(self.pos_buttons):
            self.pos_buttons[index + 1].setFocus()
        else:
            self.acquire_button.setFocus()

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

    def refresh(self, image: QImage):
        """Update the camera image in the UI."""
        self._last_image = im = Image.fromqimage(image).copy()
        draw_center_cross = self.center_cross_checkbox.isChecked()
        draw_margin = (
            self.margin_checkbox.isChecked()
            and (self.scan_config.margin_x > 0)
            and (self.scan_config.margin_y > 0)
        )
        draw = None
        if draw_center_cross or draw_margin:
            im = im.convert("RGB")
            draw = ImageDraw.Draw(im, "RGBA")
        # Draw center cross if enabled
        if draw_center_cross and draw is not None:
            color = (0, 100, 255, 150)
            draw.line(((0, im.height / 2), (im.width, im.height / 2)), fill=color)
            draw.line(((im.width / 2, 0), (im.width / 2, im.height)), fill=color)
        # Draw margins rect if enabled
        if draw_margin and draw is not None:
            color = (0, 100, 255, 200)
            x1 = self.scan_config.margin_x - 1
            y1 = self.scan_config.margin_y - 1
            x2 = self.camera.width - self.scan_config.margin_x
            y2 = self.camera.height - self.scan_config.margin_y
            draw.rectangle((x1, y1, x2, y2), outline=color)
        b = im.convert("RGBA").tobytes()
        qim = QImage(b, im.width, im.height, QImage.Format.Format_RGBA8888)
        self.image_label.setPixmap(QPixmap.fromImage(qim))

    def camera_rotation_test(self):
        """Takes a second image to visualize camera angle."""
        # Fetch current position
        start_pos = self.stage.position
        # Get magnification, required to calculate table displacement
        mag = self.camera.objective
        disp_x = (self.camera.pixel_size_in_um[0] / mag) * self.camera.width
        # Calculate side pos and move stage
        side_pos = (start_pos[0] + disp_x, start_pos[1], start_pos[2])
        self.stage.stage.wait_routine = lambda: (print('routine'))
        print("move")
        self.stage.move_to(Vector(*side_pos), wait=True, backlash=True)
        # Wait for 2 seconds
        print("wait")
        d = 20
        while d > 0:
            time.sleep(0.1)
            d -= 1
            QApplication.processEvents()
        # Take image
        print("wait done")
        im = self.camera.get_last_qimage()
        self.image_label_right.setPixmap(QPixmap.fromImage(im))
        self.image_label_right.show()
        # Return to starting position
        print("moveback")
        self.stage.move_to(start_pos, wait=True, backlash=True)
        print("moveback done")
        # self.instruments.stage.enable_joystick()




    def save_settings(self):
        """
        Save some settings in the settings.yaml file.
        """
        data: dict[str, Any] = {}

        # Camera settings
        if self.instruments.camera is not None:
            data["camera"] = self.instruments.camera.settings

        # Focus
        if self.instruments.focus_helper is not None:
            data["focus"] = self.instruments.focus_helper.settings

        yaml.dump(data, open("settings.yaml", "w"))

    def reload_settings(self):
        """
        Restore settings in the settings.yaml file.
        """
        data = yaml.load(open("chipscan_settings.yaml", "r"), yaml.SafeLoader)
        # Camera settings (maybe missing from settings)
        camera = data.get("camera")
        if (self.instruments.camera is not None) and (camera is not None):
            self.instruments.camera.settings = camera
            if self.viewer.stage_sight is not None:
                self.viewer.stage_sight.distortion = (
                    self.instruments.camera.correction_matrix
                )
        # Focus
        focus = data.get("focus")
        if self.instruments.focus_helper is not None and focus is not None:
            self.instruments.focus_helper.settings = focus

