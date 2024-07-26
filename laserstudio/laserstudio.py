#!/usr/bin/python3
from PyQt6.QtCore import Qt, QKeyCombination, QSettings
from PyQt6.QtGui import QColor, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow,
    QButtonGroup,
)
from typing import Optional, Any

from .widgets.viewer import Viewer
from .instruments.instruments import (
    Instruments,
    PDMInstrument,
    LaserDriverInstrument,
    CameraNITInstrument,
)
from .instruments.stage import Vector
from .widgets.toolbars import (
    PictureToolbar,
    ZoomToolbar,
    ScanToolbar,
    StageToolbar,
    CameraToolbar,
    MainToolbar,
    MarkersToolbar,
    PDMToolbar,
    LaserDriverToolbar,
    CameraNITToolBar,
)
import yaml
from .restserver.server import RestProxy
from PIL import Image, ImageQt


class LaserStudio(QMainWindow):
    def __init__(self, config: Optional[dict]):
        """
        Laser Studio main window.

        :param config: Optional configuration dictionary.
        """
        super().__init__()

        if config is None:
            config = {}

        # User settings
        self.settings = QSettings("ledger", "laserstudio")

        # Instantiate all instruments
        self.instruments = Instruments(config)

        # Creation of Viewer as the central widget
        self.viewer = Viewer()
        self.setCentralWidget(self.viewer)

        # Add StageSight if there is a Stage instrument or a camera
        if self.instruments.stage is not None or self.instruments.camera is not None:
            self.viewer.add_stage_sight(
                self.instruments.stage,
                self.instruments.camera,
                self.instruments.probes + self.instruments.lasers,
            )
            self.viewer.reset_camera()

        # Create group of buttons for Viewer mode selection
        self.viewer_buttons_group = group = QButtonGroup(self)
        group.idClicked.connect(
            lambda _id: self.viewer.__setattr__("mode", Viewer.Mode(_id))
        )
        self.viewer.mode_changed.connect(self.update_buttons_mode)

        # Toolbar: Main
        toolbar = MainToolbar(self)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

        # Toolbar: Background picture
        toolbar = PictureToolbar(self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        # Toolbar: Zoom
        toolbar = ZoomToolbar(self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        # Toolbar: Markers
        toolbar = MarkersToolbar(self.viewer)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        # Toolbar: Stage positioning
        if self.instruments.stage is not None:
            toolbar = StageToolbar(self)
            self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, toolbar)

        # Toolbar: Scanning zone definition and usage
        toolbar = ScanToolbar(self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        # Toolbar: Camera Image control
        if self.instruments.camera is not None:
            toolbar = CameraToolbar(self)
            self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, toolbar)

        # Toolbar: NIT Camera Image control
        if isinstance(self.instruments.camera, CameraNITInstrument):
            toolbar = CameraNITToolBar(self)
            self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, toolbar)

        # Laser toolbars
        for i, laser in enumerate(self.instruments.lasers):
            if isinstance(laser, PDMInstrument):
                toolbar = PDMToolbar(self, i)
            elif isinstance(laser, LaserDriverInstrument):
                toolbar = LaserDriverToolbar(self, i)
            else:
                continue
            self.addToolBar(Qt.ToolBarArea.RightToolBarArea, toolbar)

        # Instantiate proxy for REST command reception
        self.rest_proxy = RestProxy(self)

        # Create shortcuts
        shortcut = QShortcut(Qt.Key.Key_Escape, self)
        shortcut.activated.connect(
            lambda: self.viewer.__setattr__("mode", Viewer.Mode.NONE)
        )
        shortcut = QShortcut(Qt.Key.Key_R, self)
        shortcut.activated.connect(
            lambda: self.viewer.__setattr__("mode", Viewer.Mode.ZONE)
        )
        # shortcut = QShortcut(Qt.Key_T, self)
        # shortcut.activated.connect(self.zone_rot_mode)
        shortcut = QShortcut(Qt.Key.Key_M, self)
        shortcut.activated.connect(
            lambda: self.viewer.__setattr__("mode", Viewer.Mode.STAGE)
        )
        shortcut = QShortcut(Qt.Key.Key_P, self)
        shortcut.activated.connect(
            lambda: self.viewer.__setattr__("mode", Viewer.Mode.PIN)
        )
        if (stage := self.instruments.stage) is not None:
            shortcut = QShortcut(Qt.Key.Key_PageUp, self)
            shortcut.activated.connect(
                lambda: stage.move_relative(Vector(0, 0, 1), wait=True)
            )
            shortcut = QShortcut(Qt.Key.Key_PageDown, self)
            shortcut.activated.connect(
                lambda: stage.move_relative(Vector(0, 0, -1), wait=True)
            )
            shortcut = QShortcut(
                QKeySequence(
                    QKeyCombination(
                        Qt.KeyboardModifier.ControlModifier, Qt.Key.Key_PageUp
                    )
                ),
                self,
            )
            shortcut.activated.connect(
                lambda: stage.move_relative(Vector(0, 0, 10), wait=True)
            )
            shortcut = QShortcut(
                QKeySequence(
                    QKeyCombination(
                        Qt.KeyboardModifier.ControlModifier, Qt.Key.Key_PageDown
                    )
                ),
                self,
            )
            shortcut.activated.connect(
                lambda: stage.move_relative(Vector(0, 0, -10), wait=True)
            )

        shortcut = QShortcut(
            QKeySequence(
                QKeyCombination(Qt.KeyboardModifier.ControlModifier, Qt.Key.Key_Space)
            ),
            self,
        )
        shortcut.activated.connect(self.handle_go_next)

        # Restore docks are previous session
        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        window_state = self.settings.value("window-state")
        if window_state is not None:
            self.restoreState(window_state)

    def closeEvent(self, event):
        """Saves user settings before closing the application."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("window-state", self.saveState())
        super().closeEvent(event)

    def handle_go_next(self) -> dict:
        """Go Next operation.
        Triggers the instruments to perform changes to go to next step of scan.
        Triggers the viewer to perform changes to go to next step of scan.
        """
        v = {}
        v.update(self.instruments.go_next())
        v.update(self.viewer.go_next())
        return v

    def handle_screenshot(self, path: Optional[str] = None) -> Image.Image:
        """
        Handle a Screenshot API to get the image of the viewer as currently displayed in laser studio.
        Either stores it to a given path (and returns a place holder pixel) or returns the image's data.

        :param path: The path where to store the viewer's image. If None, the image data is
        returned.
        :return: The Image if it has not been stored in a file, otherwise a 1x1 placeholder pixel.
        """
        # Takes the Image of the viewer as currently shown.
        pixmap = self.viewer.grab()
        if path is not None:
            pixmap.save(path)
            # Image has been saved at a given path, we return a 1x1 black pixel.
            return Image.new("1", (1, 1))
        return ImageQt.fromqpixmap(pixmap)

    def handle_camera(self, path: Optional[str] = None) -> Optional[Image.Image]:
        """
        Handle a Camera API request to get the image of the camera associated to the main Stage.
        Either stores it to a given path (and returns a place holder pixel) or returns the image's data.

        :param path: The path where to store the camera's image. If None, the image data is
            returned.
        :return: The Image if it has not been stored in a file, otherwise a 1x1 placeholder pixel.
            None if no camera exists
        """
        # Takes the Image of the camera associated to the stage.
        if self.viewer.stage_sight is None or self.viewer.stage_sight.camera is None:
            return None

        im = self.viewer.stage_sight.image.pixmap()
        if path is not None:
            im.save(path)
            # Image has been saved at a given path, we return a 1x1 black pixel.
            return Image.new("1", (1, 1))
        return ImageQt.fromqpixmap(im)

    def handle_position(self, pos: Optional[list[float]]) -> dict:
        if self.instruments.stage is None:
            return {"pos": []}
        if pos is not None:
            self.instruments.stage.move_to(Vector(*pos), wait=True)
        return {"pos": self.instruments.stage.position.data}

    def handle_add_markers(
        self, positions: Optional[list[list[float]]], color: Optional[list[float]]
    ) -> dict:
        """Add a marker.

        :param pos: The requested position(s) of the marker(s)
        :param color: The requested color of the marker(s). Defined as a list of 3 floats from 0.0 to 1.0 (RGB)
            or 4 floats from 0.0 to 1.0 (RGBA).
        :return: A dictionary containing the information about the markers' final position(s), and identifier(s)
        """
        if color is None:
            qcolor = Qt.GlobalColor.red
        else:
            if len(color) == 3:
                color.append(1.0)
            if len(color) != 4:
                ValueError(
                    "Color argument is invalid. It should be a list of 3 or 4 floats"
                )
            qcolor = QColor(
                int(color[0] * 255),
                int(color[1] * 255),
                int(color[2] * 255),
                int(color[3] * 255),
            )

        if positions is None:
            markers = [self.viewer.add_marker(None, color=qcolor)]
        else:
            markers = [
                self.viewer.add_marker((pos[0], pos[1]), color=qcolor)
                for pos in positions
            ]

        description = [
            {"id": marker.id, "pos": [marker.pos().x(), marker.pos().y()]}
            for marker in markers
        ]
        if len(description) == 1:
            return description[0]
        return {"markers": description}

    def handle_go_to_memory_point(self, index: int):
        """Perform a move operation on stage to go to a memory point.
            Memory points are defined in the configuration file, on the
            stage -> mem_points.

        :param name: The name of the memory point to go to.
        """
        if self.instruments.stage is None:
            return {"pos": []}

        if index < 0 or index >= len(self.instruments.stage.mem_points):
            return {"pos": []}

        point = self.instruments.stage.mem_points[index]

        self.instruments.stage.move_to(point, wait=True)
        return {"pos": self.instruments.stage.position.data}

    def update_buttons_mode(self, id: int):
        """Updates the button group according to the selected Viewer mode"""
        if id == self.viewer_buttons_group.checkedId():
            return
        for b in self.viewer_buttons_group.buttons():
            if id == self.viewer_buttons_group.id(b):
                b.setChecked(True)

    def save_settings(self):
        """
        Save some settings in the settings.yaml file.
        """
        data: dict[str, Any] = {}

        # Camera settings
        if self.instruments.camera is not None:
            data["camera"] = self.instruments.camera.yaml

        # Scanning geometry
        data["scangeometry"] = self.viewer.scan_geometry.yaml

        # Probes
        data["probes"] = [probe.yaml for probe in self.instruments.probes]

        # Lasers
        data["lasers"] = [laser.yaml for laser in self.instruments.lasers]

        # Viewver
        data["viewer"] = self.viewer.yaml

        yaml.dump(data, open("settings.yaml", "w"))

    def reload_settings(self):
        """
        Restore settings in the settings.yaml file.
        """
        data = yaml.load(open("settings.yaml", "r"), yaml.SafeLoader)
        # Camera settings (maybe missing from settings)
        camera = data.get("camera")
        if (self.instruments.camera is not None) and (camera is not None):
            self.instruments.camera.yaml = camera
            if self.viewer.stage_sight is not None:
                self.viewer.stage_sight.distortion = (
                    self.instruments.camera.correction_matrix
                )

        # Scanning geometry
        geometry = data.get("scangeometry")
        if geometry is not None:
            self.viewer.scan_geometry.yaml = geometry

        # Probes
        probes = data.get("probes", [])
        for pdata, probe in zip(probes, self.instruments.probes):
            probe.yaml = pdata

        # Lasers
        lasers = data.get("lasers", [])
        for pdata, laser in zip(lasers, self.instruments.lasers):
            laser.yaml = pdata

        # Viewver's configuration
        viewer = data.get("viewer")
        if viewer is not None:
            self.viewer.yaml = viewer
