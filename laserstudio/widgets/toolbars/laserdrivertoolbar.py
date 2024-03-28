from laser_driver import LaserDriverPanel
from .lasertoolbar import LaserToolbar
from laserstudio.instruments.laserdriver import LaserDriverInstrument
from typing import TYPE_CHECKING
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class LaserDriverToolbar(LaserToolbar):
    def __init__(self, laser_studio: "LaserStudio", laser_num: int):
        assert laser_num < len(laser_studio.instruments.lasers)
        self.laser = laser_studio.instruments.lasers[laser_num]
        assert isinstance(self.laser, LaserDriverInstrument)
        super().__init__(f"Laser {laser_num} (Donjon Driver)", laser_studio)
        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
        )
        self.setFloatable(True)
        self.addWidget(LaserDriverPanel(self.laser.laser))
