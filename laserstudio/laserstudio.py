#!/usr/bin/python3
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow,
    QButtonGroup,
)
from typing import Optional, Any
from .widgets.viewer import Viewer
from .instruments.instruments import Instruments
from .widgets.toolbars import (
    PictureToolbar,
    ZoomToolbar,
    ScanToolbar,
    StageToolbar,
    CameraToolbar,
    MainToolbar,
    LaserToolbar,
)
import yaml
from .restserver.server import RestProxy


class LaserStudio(QMainWindow):
    def __init__(self, config: Optional[dict]):
        """
        Laser Studio main window.

        :param config: Optional configuration dictionary.
        """
        super().__init__()

        if config is None:
            config = {}

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
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

        # Toolbar: Zoom
        toolbar = ZoomToolbar(self)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

        # Toolbar: Stage positioning
        if self.instruments.stage is not None:
            toolbar = StageToolbar(self)
            self.addToolBar(Qt.ToolBarArea.RightToolBarArea, toolbar)

        # Toolbar: Scanning zone definition and usage
        toolbar = ScanToolbar(self)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

        # Toolbar: Camera Image control
        if self.instruments.camera is not None:
            toolbar = CameraToolbar(self)
            self.addToolBar(Qt.ToolBarArea.RightToolBarArea, toolbar)

        # Laser toolbars
        for i in range(len(self.instruments.lasers)):
            toolbar = LaserToolbar(self, i)
            self.addToolBar(Qt.ToolBarArea.RightToolBarArea, toolbar)

        # Instantiate proxy for REST command reception
        self.rest_proxy = RestProxy(self)

    def handle_go_next(self):
        """Go Next operation.
        Triggers the instruments to perform changes to go to next step of scan.
        Triggers the viewer to perform changes to go to next step of scan.
        """
        self.instruments.go_next()
        self.viewer.go_next()

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
        for data, probe in zip(probes, self.instruments.probes):
            probe.yaml = data

        # Lasers
        lasers = data.get("lasers", [])
        for data, laser in zip(lasers, self.instruments.lasers):
            laser.yaml = data
