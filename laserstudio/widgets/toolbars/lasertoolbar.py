from PyQt6.QtWidgets import QToolBar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio

class LaserToolbar(QToolBar):
    def __init__(self, title: str, laser_studio: "LaserStudio", laser_num: int):
        """
        :param laser_studio: Main windows of laserstudio. Can be used for interacting with
            other elements of the UI.
        :param laser_num: Laser equipment index.
        """
        super().__init__(title)
        self.laser_studio = laser_studio
        super().setObjectName(f"toolbox-laser-{laser_num}")  # For settings save and restore
