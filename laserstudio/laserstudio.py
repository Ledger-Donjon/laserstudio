#!/usr/bin/python3
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow,
    QButtonGroup,
)
from typing import Optional, TYPE_CHECKING, Any
from .widgets.viewer import Viewer
from .instruments.instruments import Instruments
from .widgets.toolbars import (
    picture_toolbar,
    zoom_toolbar,
    scan_toolbar,
    stage_toolbar,
    camera_toolbar,
    main_toolbar,
)
import yaml

if TYPE_CHECKING:
    from .widgets.camerawizard import CameraWizard


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
            self.viewer.add_stage_sight(self.instruments.stage, self.instruments.camera)
            self.viewer.reset_camera()

        # Create group of buttons for Viewer mode selection
        self.viewer_buttons_group = group = QButtonGroup(self)
        group.idClicked.connect(
            lambda _id: self.viewer.__setattr__("mode", Viewer.Mode(_id))
        )
        self.viewer.mode_changed.connect(self.update_buttons_mode)

        # Toolbar: Main
        toolbar = main_toolbar(self)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

        # Toolbar: Background picture
        toolbar = picture_toolbar(self)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

        # Toolbar: Zoom
        toolbar = zoom_toolbar(self)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

        # Toolbar: Stage positioning
        if self.instruments.stage is not None:
            toolbar = stage_toolbar(self)
            self.addToolBar(Qt.ToolBarArea.RightToolBarArea, toolbar)

        # Toolbar: Scanning zone definition and usage
        toolbar = scan_toolbar(self)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

        # Toolbar: Camera Image control
        if self.instruments.camera is not None:
            self.camera_wizard: Optional[CameraWizard] = None
            toolbar = camera_toolbar(self)
            self.addToolBar(Qt.ToolBarArea.RightToolBarArea, toolbar)

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
