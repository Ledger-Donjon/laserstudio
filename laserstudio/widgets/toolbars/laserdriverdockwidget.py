try:
    from laser_driver import LaserDriverPanel
except Exception:
    LaserDriverPanel = None
from ...instruments.laserdriver import LaserDriverInstrument
from ..optispotcontrol import OptispotControl
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDockWidget, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class LaserDriverDockWidget(QDockWidget):
    def __init__(self, laser: LaserDriverInstrument, laser_num: int):
        """
        :param laser: Laser Driver instrument.
        :param laser_num: Laser equipment index.
        """
        assert isinstance(laser, LaserDriverInstrument)
        self.laser = laser
        super().__init__(f"Laser {laser_num} (Donjon Driver)")

        if self.laser.label:
            self.setWindowTitle(self.windowTitle() + " - " + self.laser.label)

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

        if self.laser.optispot is None:
            self.setWidget(panel)
            return

        # The driver's own panel knows nothing about the optispot, so the
        # control goes below it, in a container holding both.
        container = QWidget()
        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        container.setLayout(vbox)
        vbox.addWidget(panel)
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("Optispot:"))
        hbox.addWidget(OptispotControl(self.laser.optispot))
        vbox.addLayout(hbox)
        self.setWidget(container)
