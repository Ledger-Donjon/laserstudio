try:
    from laser_driver import LaserDriverPanel  # type: ignore
except Exception:
    LaserDriverPanel = None
from ...instruments.laserdriver import LaserDriverInstrument
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDockWidget


class LaserDriverDockWidget(QDockWidget):
    def __init__(self, laser: LaserDriverInstrument, laser_num: int):
        """
        :param laser: Laser Driver instrument.
        :param laser_num: Laser equipment index.
        """
        assert isinstance(laser, LaserDriverInstrument)
        self.laser = laser
        super().__init__(f"Laser {laser_num} (Donjon Driver)")
        self.setObjectName(
            f"toolbox-laser-donjon-{laser_num}"
        )  # For settings save and restore

        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        # Construct a UI Panel for the Laser Driver
        assert LaserDriverPanel is not None
        panel = LaserDriverPanel(self.laser.laser)
        panel.refresh_interval_edit.setMinimum(1000)
        panel.refresh_interval_edit.setMaximum(5000)
        panel.refresh_interval_edit.setValue(2000)
        self.setWidget(panel)
