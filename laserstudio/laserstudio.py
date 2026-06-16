#!/usr/bin/python3

from __future__ import annotations

import os
import logging
import yaml
from PIL import Image, ImageQt
import numpy
from numpy.typing import NDArray
from collections.abc import Sequence
from typing import Any
from PyQt6.QtCore import Qt, QKeyCombination, QSettings, QPointF
from PyQt6.QtGui import (
    QColor,
    QShortcut,
    QKeySequence,
    QGuiApplication,
    QCloseEvent,
    QColorConstants,
)
from PyQt6.QtWidgets import QMainWindow, QButtonGroup, QLabel, QToolBar, QDockWidget
from .widgets.viewer import Viewer
from .instruments.instruments import (
    Instruments,
    PDMInstrument,
    LaserDriverInstrument,
    CameraNITInstrument,
    CameraRaptorInstrument,
    LightInstrument,
)
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
from .restserver.errors import (
    DeviceUnavailableError,
    InstrumentNotFoundError,
    InvalidParameterError,
    MemoryPointNotFoundError,
)
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
                self.instruments.probes + [*self.instruments.lasers],
            )
            self.viewer.reset_camera()

        # Create group of buttons for Viewer mode selection
        self.viewer_buttons_group = group = QButtonGroup(self)

        def id_clicked(id: int):
            self.viewer.select_mode(Viewer.Mode(id), True)

        group.idClicked.connect(id_clicked)

        self.viewer.mode_changed.connect(self.update_buttons_mode)

        self.mode_indicator = QLabel()
        self.mode_indicator.setObjectName("active-mode")
        self.mode_indicator.setToolTip("Active viewer mode")
        self.mode_indicator.setProperty("modeActive", False)
        status_bar = self.statusBar()
        if status_bar is not None:
            status_bar.addPermanentWidget(self.mode_indicator)
        self.update_mode_indicator(int(self.viewer.mode))

        # ToolBar: Main
        toolbar: QToolBar = MainToolBar(self)
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
            dockwidget: QDockWidget = StageDockWidget(self)
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
        rest_config = config.get("restserver", {})
        if isinstance(rest_config, dict):
            self.rest_proxy = RestProxy(
                self,
                rest_config,
            )

        # Create shortcuts
        shortcut = QShortcut(Qt.Key.Key_Escape, self)
        shortcut.activated.connect(lambda: self.viewer.select_mode(Viewer.Mode.NONE))
        shortcut = QShortcut(Qt.Key.Key_R, self)
        shortcut.activated.connect(lambda: self.viewer.select_mode(Viewer.Mode.ZONE))
        shortcut = QShortcut(Qt.Key.Key_T, self)
        shortcut.activated.connect(
            lambda: self.viewer.select_mode(Viewer.Mode.ZONE_TILTED)
        )
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

        # Restore docks are previous session
        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        window_state = self.settings.value("window-state")
        if window_state is not None:
            self.restoreState(window_state)

    def closeEvent(self, a0: QCloseEvent | None):
        """Saves user settings before closing the application."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("window-state", self.saveState())
        # Close all other windows of the application (allWindows() are QWindow;
        # compare to this widget's native window, not self which is a QWidget).
        main_window = self.windowHandle()
        for w in QGuiApplication.allWindows():
            if w is not main_window:
                w.close()
        super().closeEvent(a0)

    def handle_go_next(self) -> Config:
        """Go Next operation.
        Triggers the instruments to perform changes to go to next step of scan.
        Triggers the viewer to perform changes to go to next step of scan.
        """
        v: Config = {}
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

    def handle_camera(self, path: str | None = None) -> Image.Image:
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
            raise DeviceUnavailableError("No camera is available.")

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
            raise DeviceUnavailableError("No camera is available.")

        if reset:
            camera.clear_averaged_images()

        # Return the number of averaged images
        return camera.number_of_averaged_images

    def handle_camera_accumulator(self, path: str | None) -> NDArray[Any]:
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
            raise DeviceUnavailableError("No camera is available.")

        frame = camera.last_frame_accumulator
        if frame is None:
            raise DeviceUnavailableError("No accumulated data is available yet.")

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
            raise DeviceUnavailableError("No camera is available.")
        if refname is not None:
            camera.current_reference_image = refname
        if dotake is not None:
            camera.take_reference_image(dotake)
        self.photoemission_dockwidget.update_ref_image_controls()
        return camera.current_reference_image

    def handle_list_instruments(self) -> list[Config]:
        """List the available instruments.

        :return: A list of dictionaries, each describing an instrument by its
            ``type`` (the instrument class name) and its ``label``.
        """
        return [
            {"type": type(inst).__name__, "label": inst.label}
            for inst in self.instruments.all_instruments
        ]

    def handle_instrument_settings(
        self, label: str, settings: Config | None
    ) -> Config:
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
        if inst is None:
            raise InstrumentNotFoundError(label)
        if settings is not None:
            inst.settings = settings
        return {"settings": inst.settings}

    def handle_position(self, pos: Sequence[float] | None) -> dict[str, Any]:
        if self.instruments.stage is None:
            raise DeviceUnavailableError("No stage is available.")
        stage = self.instruments.stage
        if pos is not None:
            if not isinstance(pos, (list, tuple)):
                current_pos = [float(v) for v in stage.position.data]
                raise InvalidParameterError(
                    "Invalid position: expected a list of coordinates.",
                    details={"pos": current_pos},
                )
            num_axis = stage.num_axis
            if len(pos) > num_axis:
                current_pos = [float(v) for v in stage.position.data]
                raise InvalidParameterError(
                    "Too many coordinates for stage axes.",
                    details={"pos": current_pos, "num_axis": num_axis},
                )
            if len(pos) < num_axis:
                target = [float(v) for v in stage.position.data]
                for i, value in enumerate(pos):
                    target[i] = value
                pos = target
            stage.move_to(Vector(*pos), wait=True)
        return {"pos": [float(v) for v in stage.position.data]}

    def handle_markers(self) -> list[Config]:
        """Handle a Markers API request to get the list of markers."""

        return [marker.to_dict() for marker in self.viewer.markers]

    def handle_add_markers(
        self,
        positions: list[list[float]] | None,
        color: list[float] | None,
        label: str | None,
        visible: bool | None = True,
    ) -> Config:
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
                raise InvalidParameterError(
                    "Color argument is invalid. It should be a list of 3 or 4 floats.",
                    details={"color": color},
                )
            qcolor = QColor(
                int(color[0] * 255),
                int(color[1] * 255),
                int(color[2] * 255),
                int(color[3] * 255),
            )

        if positions is None:
            markers = [
                self.viewer.add_marker(None, color=qcolor, label=label, visible=visible)
            ]
        else:
            markers = [
                self.viewer.add_marker(
                    (pos[0], pos[1]), color=qcolor, label=label, visible=visible
                )
                for pos in positions
            ]

        if len(markers) == 1:
            return markers[0].to_dict()
        return {"markers": [marker.to_dict() for marker in markers]}

    def handle_delete_markers(self, ids: list[int] | None = None) -> Config:
        """Delete marker(s) from the viewer.

        :param ids: The identifiers of the markers to delete. If None or empty,
            all markers are removed.
        :return: A dictionary containing the list of deleted marker identifiers
            under the ``deleted`` key.
        """
        if not ids:
            deleted = [marker.id for marker in self.viewer.markers]
            self.viewer.clear_markers()
            return {"deleted": deleted}

        id_set = set(ids)
        deleted = []
        for marker in self.viewer.markers:
            if marker.id in id_set:
                self.viewer.remove_marker(marker)
                deleted.append(marker.id)
        return {"deleted": deleted}

    def handle_pixel_to_position(self, pixels: list[list[float]]) -> Config:
        """Convert camera-image pixel coordinates into viewer coordinates.

        The conversion relies on the actual Qt scene transform of the camera
        image item, so it accounts for the camera resolution, the objective
        magnification, the stage position and any distortion applied to the
        image.

        :param pixels: A list of ``[px, py]`` pixel coordinates, with the
            origin ``(0, 0)`` at the top-left corner of the camera image.
        :return: A dictionary with the converted coordinates under the
            ``positions`` key, as a list of ``[x, y]`` viewer coordinates in
            the same order as the input.
        """
        stage_sight = self.viewer.stage_sight
        if stage_sight is None:
            raise DeviceUnavailableError("No camera (stage sight) is available.")

        image = stage_sight.image
        positions: list[list[float]] = []
        for pixel in pixels:
            if len(pixel) != 2:
                raise InvalidParameterError(
                    "Each pixel must be a [px, py] pair.",
                    details={"pixel": pixel},
                )
            scene_point = image.mapToScene(QPointF(pixel[0], pixel[1]))
            positions.append([scene_point.x(), scene_point.y()])
        return {"positions": positions}

    EMPTY_SCAN_GEOMETRY: Config = {
        "geometry": {"polygon": {"exterior": [], "interiors": []}}
    }

    def handle_scangeometry(self, settings: Config | None = None) -> Config:
        """Get or set the viewer scan geometry settings.

        :param settings: If provided, apply these settings to the scan geometry.
            If ``None``, return the current settings unchanged.
        :return: The current scan geometry settings.
        """
        if settings is not None:
            self.viewer.scan_geometry.settings = settings
        return self.viewer.scan_geometry.settings

    def handle_clear_scangeometry(self) -> Config:
        """Clear the scan geometry by setting an empty polygon."""
        self.viewer.scan_geometry.settings = self.EMPTY_SCAN_GEOMETRY
        return self.viewer.scan_geometry.settings

    def handle_go_to_memory_point(self, index: int):
        """Perform a move operation on stage to go to a memory point.
            Memory points are defined in the configuration file, on the
            stage -> mem_points.

        :param index: The index of the memory point to go to.
        """
        if self.instruments.stage is None:
            raise DeviceUnavailableError("No stage is available.")
        if index not in range(len(self.instruments.stage.mem_points)):
            raise MemoryPointNotFoundError(
                index,
                details={"available": len(self.instruments.stage.mem_points)},
            )

        point = self.instruments.stage.mem_points[index]

        self.instruments.stage.move_to(point, wait=True)
        return {"pos": self.instruments.stage.position.data}

    def update_buttons_mode(self, id: int):
        """Updates the button group according to the selected Viewer mode"""
        self.update_mode_indicator(id)
        if id == self.viewer_buttons_group.checkedId():
            return
        for b in self.viewer_buttons_group.buttons():
            if id == self.viewer_buttons_group.id(b):
                b.setChecked(True)

    def update_mode_indicator(self, id: int):
        """Update the mode indicator label."""
        try:
            mode = Viewer.Mode(id)
        except ValueError:
            mode = Viewer.Mode.NONE
        self.mode_indicator.setText(self._mode_label(mode))
        self.mode_indicator.setProperty("modeActive", mode != Viewer.Mode.NONE)
        style = self.mode_indicator.style()
        if style is not None:
            style.unpolish(self.mode_indicator)
            style.polish(self.mode_indicator)
        self.mode_indicator.update()

    def _mode_label(self, mode: Viewer.Mode) -> str:
        labels = {
            Viewer.Mode.NONE: "Mode: None (Esc)",
            Viewer.Mode.STAGE: "Mode: Move (M)",
            Viewer.Mode.ZONE: "Mode: Zone (R)",
            Viewer.Mode.ZONE_TILTED: "Mode: Tilted Zone (T)",
            Viewer.Mode.ZONE_POLY: "Mode: Poly Zone",
            Viewer.Mode.PIN: "Mode: Pin (P)",
            Viewer.Mode.OFFSET_ORIGIN: "Mode: Offset",
        }
        return labels.get(mode, f"Mode: {mode.name}")

    def save_settings(self) -> None:
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
        lasers_settings = list[dict[str, Any]]()
        for laser in self.instruments.lasers:
            laser_settings = laser.settings
            if laser_settings.get("on_off", False):
                logging.getLogger("laserstudio").warning(
                    f"Laser {laser.label} is currently on. "
                    "To prevent any risk to be set on during setting restoration, "
                    "the parameter 'on_off' is not saved in the settings file."
                )
            _ = laser_settings.pop("on_off", None)
            lasers_settings.append(laser_settings)
        data["lasers"] = lasers_settings

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
        try:
            data = yaml.load(open("settings.yaml", "r"), yaml.SafeLoader)
        except FileNotFoundError:
            logging.getLogger("laserstudio").warning(
                "Settings file not found in directory " + os.getcwd()
            )
            return
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
            if "on_off" in pdata:
                logging.getLogger("laserstudio").warning(
                    f"Laser {laser.label} is currently on. "
                    "To prevent any risk during settings restoration, "
                    "the parameter 'on_off' is ignored from the settings."
                )
            _ = pdata.pop("on_off", None)
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
        Set the log level of the application and instrument loggers.
        """
        logging.getLogger("laserstudio").setLevel(level)
        self.instruments.set_log_level(level)
