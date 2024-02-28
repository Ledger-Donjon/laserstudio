from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QToolBar,
    QPushButton,
    QHBoxLayout,
    QWidget,
    QComboBox,
)
from ...util import resource_path
from ..keyboardbox import KeyboardBox

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class StageToolbar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio"):
        assert laser_studio.instruments.stage is not None
        self.stage = laser_studio.instruments.stage
        super().__init__("Stage control", laser_studio)
        group = laser_studio.viewer_buttons_group
        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
        )
        self.setFloatable(True)

        # Activate stage-move mode
        w = QPushButton(self)
        w.setToolTip("Move stage mode")
        w.setIcon(
            QIcon(resource_path(":/icons/fontawesome-free/directions-solid-24.png"))
        )
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        self.addWidget(w)
        group.addButton(w)
        group.setId(w, laser_studio.viewer.Mode.STAGE)

        self.mem_point_selector = box = QComboBox()
        for i in range(len(self.stage.mem_points)):
            box.addItem(f"Go to M{i}")
        box.activated.connect(
            lambda i: self.stage.move_to(self.stage.mem_points[i], wait=True)
        )
        self.addWidget(box)
        box.setHidden(len(self.stage.mem_points) == 0)

        w = QPushButton(self)
        w.setText("Home")
        w.clicked.connect(self.stage.stage.home)
        self.addWidget(w)

        # Keyboard box
        w = KeyboardBox(self.stage)
        self.addWidget(w)
