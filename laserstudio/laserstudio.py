#!/usr/bin/python3
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QMainWindow,
    QGridLayout,
    QLabel,
    QToolBar,
    QWidget,
    QPushButton,
    QButtonGroup,
)
from PyQt6.QtGui import QPixmap, QIcon
from typing import Optional
from .util import resource_path
from .widgets.viewer import Viewer
from .instruments.instruments import Instruments


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

        toolbar = QToolBar(self)
        toolbar.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
        )
        toolbar.setFloatable(False)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

        # Icon Logo
        w = QLabel()
        w.setPixmap(
            QPixmap(resource_path(":/icons/logo.png")).scaled(
                64, 64, transformMode=Qt.TransformationMode.SmoothTransformation
            )
        )
        w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(w)

        # Create a grid for Viewer mode selection buttons
        layout = QGridLayout()
        w = QWidget()
        w.setLayout(layout)
        layout.setHorizontalSpacing(0)
        layout.setVerticalSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        toolbar.addWidget(w)

        self.viewer_buttons_group = group = QButtonGroup(toolbar)
        group.idClicked.connect(
            lambda _id: self.viewer.__setattr__("mode", Viewer.Mode(_id))
        )

        # Button to unselect any viewer mode.
        w = QPushButton(toolbar)
        w.setToolTip("Cancel any mode")
        w.setIcon(QIcon(resource_path(":/icons/icons8/cursor.png")))
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        w.setChecked(True)
        layout.addWidget(w, 1, 1)
        group.addButton(w)
        group.setId(w, int(Viewer.Mode.NONE))

        # Button to select stage move mode.
        w = QPushButton(toolbar)
        w.setToolTip("Move stage mode")
        w.setIcon(
            QIcon(resource_path(":/icons/fontawesome-free/directions-solid-24.png"))
        )
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        layout.addWidget(w, 1, 2)
        group.addButton(w)
        group.setId(w, int(Viewer.Mode.STAGE))

        # Button to select zoning mode.
        w = QPushButton(toolbar)
        w.setToolTip("Define scanning regions")
        w.setIcon(QIcon(resource_path(":/icons/icons8/region.png")))
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        layout.addWidget(w, 2, 1)
        group.addButton(w)
        group.setId(w, int(Viewer.Mode.ZONE))

        # Button to select Pining mode.
        w = QPushButton(toolbar)
        w.setToolTip("Pin mode")
        w.setIcon(QIcon(resource_path(":/icons/icons8/pin.png")))
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        layout.addWidget(w, 2, 2)
        group.addButton(w)
        group.setId(w, int(Viewer.Mode.PIN))

        self.viewer.mode_changed.connect(self.update_buttons_mode)

        # Button to load background picture.
        w = QPushButton(toolbar)
        w.setToolTip("Load background picture from file")
        w.setIcon(QIcon(resource_path(":/icons/icons8/picture.png")))
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(self.viewer.load_picture)
        toolbar.addWidget(w)

        if self.viewer.stage_sight is not None:
            # Button to toggle off or on the camera image presentation
            w = QPushButton(toolbar)
            w.setToolTip("Show/Hide Image")
            w.setCheckable(True)
            w.setChecked(True)
            icon = QIcon()
            icon.addPixmap(
                QPixmap(resource_path(":/icons/fontawesome-free/video-solid-24.png")),
                QIcon.Mode.Normal,
                QIcon.State.On,
            )
            icon.addPixmap(
                QPixmap(
                    resource_path(":/icons/fontawesome-free/video-slash-solid-24.png")
                ),
                QIcon.Mode.Normal,
                QIcon.State.Off,
            )
            w.setIcon(icon)
            w.setIconSize(QSize(24, 24))
            w.toggled.connect(
                lambda b: self.viewer.stage_sight.__setattr__("show_image", b)
            )
            toolbar.addWidget(w)

        # Button to trigger a Go Next
        w = QPushButton(toolbar)
        w.setToolTip("Go Next Scan Point")
        w.setIcon(
            QIcon(resource_path(":/icons/fontawesome-free/forward-step-solid-24.png"))
        )
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(self.handle_go_next)
        toolbar.addWidget(w)

        toolbar = QToolBar(self)
        toolbar.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
        )
        toolbar.setFloatable(False)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

        # Zoom in.
        w = QPushButton(toolbar)
        w.setText("Z+")
        w.setToolTip("Zoom in")
        w.clicked.connect(
            lambda: self.viewer.__setattr__("zoom", self.viewer.zoom * 2.0)
        )
        toolbar.addWidget(w)

        # Zoom out.
        w = QPushButton(toolbar)
        w.setText("Z-")
        w.setToolTip("Zoom out")
        w.clicked.connect(
            lambda: self.viewer.__setattr__("zoom", self.viewer.zoom * 0.5)
        )
        toolbar.addWidget(w)

        # Zoom 1.
        w = QPushButton(toolbar)
        w.setText("Z:1x")
        w.setToolTip("Reset zoom")
        w.clicked.connect(lambda: self.viewer.__delattr__("zoom"))
        toolbar.addWidget(w)

        # Button to reset the zoom.
        w = QPushButton(toolbar)
        w.setToolTip("Reset Viewer to see all elements")
        w.setIcon(QIcon(resource_path(":/icons/icons8/zoom-reset.png")))
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(self.viewer.reset_camera)
        toolbar.addWidget(w)

        # Button to enable/disable StageSight position tracking.
        w = QPushButton(toolbar)
        w.setToolTip("Follow stage")
        w.setCheckable(True)
        w.setIcon(
            QIcon(resource_path(":/icons/fontawesome-free/arrows-to-dot-solid-24.png"))
        )
        w.setIconSize(QSize(24, 24))
        w.toggled.connect(self.viewer.follow_stagesight)
        w.setChecked(True)
        toolbar.addWidget(w)

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
