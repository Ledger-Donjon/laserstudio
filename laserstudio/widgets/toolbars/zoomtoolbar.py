from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QToolBar, QPushButton
from ...utils.util import colored_image
from ..coloredbutton import ColoredPushButton

if TYPE_CHECKING:
    from ...widgets.viewer import Viewer


class ZoomToolbar(QToolBar):
    def __init__(self, viewer: "Viewer"):
        super().__init__("Zoom control")
        self.setObjectName("toolbar-zoom")  # For settings save and restore
        self.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        self.setFloatable(True)

        # Zoom in (*2).
        w = QPushButton(self)
        w.setToolTip("Zoom in")
        w.setIcon(
            QIcon(
                colored_image(
                    ":/icons/fontawesome-free/magnifying-glass-plus-solid.svg"
                )
            )
        )
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(lambda: viewer.__setattr__("zoom", viewer.zoom * 2.0))
        self.addWidget(w)

        # Zoom out (/2).
        w = QPushButton(self)
        w.setToolTip("Zoom out")
        w.setIcon(
            QIcon(
                colored_image(
                    ":/icons/fontawesome-free/magnifying-glass-minus-solid.svg"
                )
            )
        )
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(lambda: viewer.__setattr__("zoom", viewer.zoom * 0.5))
        self.addWidget(w)

        # Zoom reset (1:1).
        w = QPushButton(self)
        w.setToolTip("Reset zoom")
        w.setIcon(QIcon(colored_image(":/icons/magnifying-glass-one-solid.svg")))
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(lambda: viewer.__delattr__("zoom"))
        self.addWidget(w)

        # Zoom to all.
        w = QPushButton(self)
        w.setToolTip("Reset Viewer to see all elements")
        w.setIcon(QIcon(colored_image(":/icons/magnifying-glass-all-solid.svg")))
        w.setIconSize(QSize(24, 24))
        w.clicked.connect(viewer.reset_camera)
        self.addWidget(w)

        # Button to enable/disable StageSight position tracking.
        w = ColoredPushButton(
            icon_path=":/icons/fontawesome-free/arrows-to-dot-solid.svg", parent=self
        )
        w.setToolTip("Center on focused item")
        w.setCheckable(True)
        w.setIconSize(QSize(24, 24))
        w.toggled.connect(lambda x: viewer.__setattr__("follow_stage_sight", x))
        viewer.follow_stage_sight_changed.connect(w.setChecked)
        w.setChecked(True)
        self.addWidget(w)

        # Position tracking label
        self.position = QPushButton("Cursor Position")
        self.position.setToolTip(
            "When activated, this button shows the cursor's position in the viewer"
        )
        self.position.setCheckable(True)
        self.position.toggled.connect(self.activate_mouse_tracking)
        self.position_signal = viewer.mouse_moved
        self.addWidget(self.position)
        self.position.setChecked(True)

    def activate_mouse_tracking(self, activate: bool):
        if not activate:
            self.position.setText("Cursor Position")
            self.position_signal.disconnect(self.update_position)
        else:
            self.position_signal.connect(self.update_position)

    def update_position(self, x: float, y: float):
        self.position.setText(f"{x:.02f}µm {y:.02f}µm")
