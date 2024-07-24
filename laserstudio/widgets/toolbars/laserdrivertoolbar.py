try:
    from laser_driver import LaserDriverPanel  # type: ignore
except Exception:
    LaserDriverPanel = None
from .lasertoolbar import LaserToolbar
from ...instruments.laserdriver import LaserDriverInstrument
from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class LaserDriverToolbar(LaserToolbar):
    def __init__(self, laser_studio: "LaserStudio", laser_num: int):
        """
        :param laser_studio: Main windows of laserstudio. Can be used for interacting with
            other elements of the UI.
        :param laser_num: Laser equipment index.
        """
        assert LaserDriverPanel is not None
        assert laser_num < len(laser_studio.instruments.lasers)
        self.laser = laser_studio.instruments.lasers[laser_num]
        assert isinstance(self.laser, LaserDriverInstrument)
        super().__init__(f"Laser {laser_num} (Donjon Driver)", laser_studio, laser_num)
        super().setObjectName(f"toolbox-laser-donjon-{laser_num}")  # For settings save and restore
        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
        )
        self.setFloatable(True)
        panel = LaserDriverPanel(self.laser.laser)
        panel.refresh_interval_edit.setMinimum(1000)
        panel.refresh_interval_edit.setMaximum(5000)
        panel.refresh_interval_edit.setValue(2000)
        self.addWidget(panel)
