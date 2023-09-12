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
        assert toolbar

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

        group = QButtonGroup(toolbar)
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

        # Button to reset the zoom.
        w = QPushButton(toolbar)
        w.setToolTip("Reset Viewer to see all elements")
        w.setIcon(QIcon(resource_path(":/icons/icons8/zoom-reset.png")))
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(self.viewer.reset_camera)
        toolbar.addWidget(w)
