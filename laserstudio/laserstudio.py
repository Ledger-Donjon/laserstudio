#!/usr/bin/python3
from PyQt6.QtCore import Qt, QKeyCombination, QSettings
from PyQt6.QtGui import (
    QColor,
    QShortcut,
    QKeySequence,
    QGuiApplication,
    QCloseEvent,
    QColorConstants,
)
from PyQt6.QtWidgets import QMainWindow, QButtonGroup
from typing import Any
from .widgets.viewer import Viewer
from .instruments.instruments import (
    Instruments,
    PDMInstrument,
    LaserDriverInstrument,
    CameraNITInstrument,
    CameraRaptorInstrument,
    LightInstrument,
)
import logging
import yaml
from PIL import Image, ImageQt
import numpy

from .instruments.stage import Vector
from .widgets.toolbars import (
    PictureToolBar,
    ZoomToolBar,
    ScanToolBar,
    StageDockWidget,
    CameraDockWidget,
    CameraImageAdjustementDockWidget,
    MainToolBar,
    MarkersToolBar,
    PDMDockWidget,
    LaserDriverDockWidget,
    CameraNITDockWidget,
    CameraRaptorDockWidget,
    PhotoEmissionDockWidget,
    LightDockWidget,
    FocusToolBar,
)
from .restserver.server import RestProxy
from .utils.yaml_types import Config


class LaserStudio(QMainWindow):
    """
    Laser Studio main class and main window.
    """

    def __init__(self, config_file: Config | None):
        """
        Initialize the Laser Studio main window.

        :param config: Optional configuration dictionary.
            If None, an empty configuration is used.
        """
        super().__init__()

        config: Config = {} if config_file is None else config_file

        # Configuration file
        self.config = config

        # Permits for the user to deactivate temporarly the go_next effect
        self.scanning_enabled = True

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

        def id_clicked(id: int):
            self.viewer.select_mode(Viewer.Mode(id), True)

        group.idClicked.connect(id_clicked)

        self.viewer.mode_changed.connect(self.update_buttons_mode)

        # ToolBar: Main
        toolbar = MainToolBar(self)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

        # ToolBar: Background picture
        toolbar = PictureToolBar(self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        # ToolBar: Zoom
        toolbar = ZoomToolBar(self.viewer)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        # ToolBar: Markers
        toolbar = MarkersToolBar(self.viewer)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        # Dock widget: Markers list
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, toolbar.markers_list_dockwidget
        )

        # ToolBar: Stage positioning
        if self.instruments.stage is not None:
            dockwidget = StageDockWidget(self)
            self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dockwidget)

        # ToolBar: Focusing
        if (
            self.instruments.stage is not None
            and self.instruments.stage.num_axis > 2
            and self.instruments.camera is not None
            and self.instruments.focus_helper is not None
        ):
            toolbar = FocusToolBar(
                self.instruments.stage,
                self.instruments.camera,
                self.instruments.focus_helper,
            )
            self.addToolBar(toolbar)

            self.addDockWidget(
                Qt.DockWidgetArea.RightDockWidgetArea,
                toolbar.magic_focus_dockwidget,
            )
            self.tabifyDockWidget(
                toolbar.magic_focus_dockwidget,
                toolbar.magic_focus_settings_dockwidget,
            )

        # ToolBar: Scanning zone definition and usage
        toolbar = ScanToolBar(self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        # Dock widget: Camera Image control
        if self.instruments.camera is not None:
            if isinstance(self.instruments.camera, CameraRaptorInstrument):
                dockwidget = CameraRaptorDockWidget(self)
            else:
                dockwidget = CameraDockWidget(self)
            self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dockwidget)
            self.addDockWidget(
                Qt.DockWidgetArea.BottomDockWidgetArea,
                CameraImageAdjustementDockWidget(self),
            )

            self.photoemission_dockwidget = PhotoEmissionDockWidget(self)
            self.addDockWidget(
                Qt.DockWidgetArea.BottomDockWidgetArea, self.photoemission_dockwidget
            )

        # Dock widget: NIT Camera Image control extra panel
        if isinstance(self.instruments.camera, CameraNITInstrument):
            dockwidget = CameraNITDockWidget(self)
            self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dockwidget)

        # Dock widgets: Lasers
        for i, laser in enumerate(self.instruments.lasers):
            if isinstance(laser, PDMInstrument):
                dockwidget = PDMDockWidget(laser, i)
            elif isinstance(laser, LaserDriverInstrument):
                dockwidget = LaserDriverDockWidget(laser, i)
            else:
                continue
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dockwidget)

        # Dock widget: Light
        if isinstance(self.instruments.light, LightInstrument):
            dockwidget = LightDockWidget(self.instruments.light)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dockwidget)

        # Instantiate proxy for REST command reception
        self.rest_proxy = RestProxy(self, config.get("restserver", {}))

        # Create shortcuts
        shortcut = QShortcut(Qt.Key.Key_Escape, self)
        shortcut.activated.connect(lambda: self.viewer.select_mode(Viewer.Mode.NONE))
        shortcut = QShortcut(Qt.Key.Key_R, self)
        shortcut.activated.connect(lambda: self.viewer.select_mode(Viewer.Mode.ZONE))
        # shortcut = QShortcut(Qt.Key_T, self)
        # shortcut.activated.connect(self.zone_rot_mode)
        shortcut = QShortcut(Qt.Key.Key_M, self)
        shortcut.activated.connect(lambda: self.viewer.select_mode(Viewer.Mode.STAGE))
        shortcut = QShortcut(Qt.Key.Key_P, self)
        shortcut.activated.connect(lambda: self.viewer.select_mode(Viewer.Mode.PIN))
        if (stage := self.instruments.stage) is not None and stage.num_axis > 2:
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

        logging.getLogger("laserstudio").debug("LaserStudio initialized")

        # # Restore docks are previous session
        # geometry = self.settings.value("geometry")
        # if geometry is not None:
        #     self.restoreGeometry(geometry)
        # window_state = self.settings.value("window-state")
        # if window_state is not None:
        #     self.restoreState(window_state)

    def closeEvent(self, a0: QCloseEvent | None):
        """Saves user settings before closing the application."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("window-state", self.saveState())
        # Close all other windows of the application
        for w in QGuiApplication.allWindows():
            if w != self:
                w.close()
        super().closeEvent(a0)

    def handle_go_next(self) -> dict[str, Any]:
        """Go Next operation.
        Triggers the instruments to perform changes to go to next step of scan.
        Triggers the viewer to perform changes to go to next step of scan.
        """
        v: dict[str, Any] = {}
        v.update(self.instruments.go_next())
        v.update(self.viewer.go_next())
        return v

    def handle_screenshot(self, path: str | None = None) -> Image.Image:
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

    def handle_camera(self, path: str | None = None) -> Image.Image | None:
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

    def handle_camera_average(self, reset: bool):
        """
        Handle a Camera API request to get the average count of the camera associated to the main Stage.

        :param reset: If True, reset the camera's accumulator.
        :return: The current number of accumulated images.
            None if no camera exists
        """
        # Takes the Image of the camera associated to the stage.
        if (
            self.viewer.stage_sight is None
            or (camera := self.viewer.stage_sight.camera) is None
        ):
            return None

        if reset:
            camera.clear_averaged_images()

        # Return the number of averaged images
        return camera.number_of_averaged_images

    def handle_camera_accumulator(self, path: str | None) -> numpy.ndarray | None:
        """
        Handle a Camera API request to get the accumulated image of the camera.
        Either stores it to a given path (and returns a place holder pixel) or returns the accumulator's data.

        :param path: The path where to store the accumulator's data.
            If None, the data is returned.
        :return: The camera's accumulator's data if it has not been stored in a file.
            Otherwise, an empty array.
        """
        # Takes the Image of the camera associated to the stage.
        if (
            self.viewer.stage_sight is None
            or (camera := self.viewer.stage_sight.camera) is None
        ):
            return None

        frame = camera.last_frame_accumulator
        if frame is None:
            return None

        if path is not None:
            numpy.save(path, frame)
            # Image has been saved at a given path, we return an empty array.
            return numpy.array([])
        return frame

    def handle_camera_reference(self, dotake: bool | None, refname: str | None):
        """
        Handles camera reference image operations.

        This method manages the camera's reference image by allowing the user to set
        the current reference image or take a new one.

        :param dotake: If True, a new reference image will be taken. If False, no new
                       image will be taken. If None, no action is performed.
        :param refname: The name of reference image to set as the current reference
                       image for the camera. If None, no action is performed.
        :returns: None if the stage sight or its associated camera is unavailable,
                  otherwise returns the current reference image name.
        """
        # Takes the camera associated to the stage.
        if (
            self.viewer.stage_sight is None
            or (camera := self.viewer.stage_sight.camera) is None
        ):
            return
        if refname is not None:
            camera.current_reference_image = refname
        if dotake is not None:
            camera.take_reference_image(dotake)
        self.photoemission_dockwidget.update_ref_image_controls()
        return camera.current_reference_image

    def handle_instrument_settings(
        self, label: str, settings: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """
        Handles the settings for a specific instrument identified by its label.
        This method retrieves an instrument by its label, updates its settings if
        provided, and returns the updated settings.

        :param label: The label identifying the instrument.
        :param settings: A dictionary containing the settings to be
            applied to the instrument. If None, the instrument's settings
            remain unchanged.
        :return: A dictionary containing the updated settings of the
            instrument if the instrument is found, otherwise None.
        """
        inst = self.instruments.get_instrument_with_label(label)
        if inst is not None:
            if settings is not None:
                inst.settings = settings
            return {"settings": inst.settings}
        return None

    def handle_position(self, pos: list[float] | None) -> dict[str, Any]:
        if self.instruments.stage is None:
            return {"pos": []}
        if pos is not None:
            self.instruments.stage.move_to(Vector(*pos), wait=True)
        return {"pos": self.instruments.stage.position.data}

    def handle_markers(self) -> list[dict[str, Any]]:
        """Handle a Markers API request to get the list of markers."""

        return [marker.to_dict() for marker in self.viewer.markers]

    def handle_add_markers(
        self,
        positions: list[list[float]] | None,
        color: list[float] | None,
        label: str | None,
        visible: bool | None = True,
    ) -> dict[str, Any]:
        """Add marker(s).

        :param positions: The requested position(s) of the marker(s).
        :param color: The requested color of the marker(s). Defined as a list of 3 floats from 0.0 to 1.0 (RGB)
            or 4 floats from 0.0 to 1.0 (RGBA).
        :param label: The requested label of the marker(s).
        :param visible: If False, marker(s) are created but not displayed (setVisible(False)).
        :return: A dictionary containing the information about the markers' final position(s), and identifier(s)
        """
        if visible is None:
            visible = True
        if color is None:
            qcolor = QColorConstants.Red
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
            markers = [
                self.viewer.add_marker(
                    None, color=qcolor, label=label, visible=visible
                )
            ]
        else:
            markers = [
                self.viewer.add_marker(
                    (pos[0], pos[1]), color=qcolor, label=label, visible=visible
                )
                for pos in positions
            ]

        description = [marker.to_dict() for marker in markers]
        if len(description) == 1:
            return description[0]
        return {"markers": description}

    def handle_go_to_memory_point(self, index: int):
        """Perform a move operation on stage to go to a memory point.
            Memory points are defined in the configuration file, on the
            stage -> mem_points.

        :param index: The index of the memory point to go to.
        """
        if self.instruments.stage is None or index not in range(
            len(self.instruments.stage.mem_points)
        ):
            return {"pos": list[float]()}

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
            data["camera"] = self.instruments.camera.settings

        # Scanning geometry
        data["scangeometry"] = self.viewer.scan_geometry.settings

        # Lighting
        if self.instruments.light is not None:
            data["light"] = self.instruments.light.settings

        # Probes
        data["probes"] = [probe.settings for probe in self.instruments.probes]

        # Lasers
        data["lasers"] = [laser.settings for laser in self.instruments.lasers]

        # Focus
        if self.instruments.focus_helper is not None:
            data["focus"] = self.instruments.focus_helper.settings

        # Viewer
        data["viewer"] = self.viewer.settings

        # Stage
        if self.instruments.stage is not None:
            data["stage"] = self.instruments.stage.settings

        yaml.dump(data, open("settings.yaml", "w"))

    def reload_settings(self):
        """
        Restore settings in the settings.yaml file.
        """
        data = yaml.load(open("settings.yaml", "r"), yaml.SafeLoader)
        # Camera settings (maybe missing from settings)
        camera = data.get("camera")
        if (self.instruments.camera is not None) and (camera is not None):
            self.instruments.camera.settings = camera
            if self.viewer.stage_sight is not None:
                self.viewer.stage_sight.distortion = (
                    self.instruments.camera.correction_matrix
                )

        # Lighting system settings
        lighting = data.get("lighting")
        if (self.instruments.light is not None) and (lighting is not None):
            self.instruments.light.settings = lighting

        # Scanning geometry
        geometry = data.get("scangeometry")
        logging.getLogger("laserstudio").debug(f"Scan Geometry settings: {geometry}...")
        if geometry is not None:
            self.viewer.scan_geometry.settings = geometry

        # Probes
        probes = data.get("probes", [])
        for pdata, probe in zip(probes, self.instruments.probes):
            probe.settings = pdata

        # Lasers
        lasers = data.get("lasers", [])
        for pdata, laser in zip(lasers, self.instruments.lasers):
            laser.settings = pdata

        # Focus
        focus = data.get("focus")
        if self.instruments.focus_helper is not None and focus is not None:
            self.instruments.focus_helper.settings = focus

        # Viewer's configuration
        viewer = data.get("viewer")
        if viewer is not None:
            self.viewer.settings = viewer

        # Stage
        stage = data.get("stage")
        if self.instruments.stage is not None and stage is not None:
            self.instruments.stage.settings = stage

    def set_log_level(self, level: int):
        """
        Set the log level of the logger "laserstudio".
        """
        logging.getLogger("laserstudio").setLevel(level)
