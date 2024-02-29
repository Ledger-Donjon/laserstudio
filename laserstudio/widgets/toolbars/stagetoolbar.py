from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QToolBar,
    QPushButton,
    QComboBox,
)
from ...utils.util import resource_path
from ..keyboardbox import KeyboardBox
from ...instruments.stage import MoveFor

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

        # Move for
        self.move_for_selector = box = QComboBox()
        box.addItem("Camera", userData=MoveFor(MoveFor.Type.CAMERA_CENTER))
        for i in range(len(laser_studio.instruments.lasers)):
            box.addItem(f"Laser {i+1}", userData=MoveFor(MoveFor.Type.LASER, i))
        for i in range(len(laser_studio.instruments.probes)):
            box.addItem(f"Probe {i+1}", userData=MoveFor(MoveFor.Type.PROBE, i))
        box.activated.connect(self.move_for_selection)
        self.addWidget(box)

    def move_for_selection(self, index: int):
        move_for = self.move_for_selector.itemData(index, Qt.ItemDataRole.UserRole)
        if not isinstance(move_for, MoveFor):
            return
        self.stage.move_for = move_for
