from PyQt6.QtWidgets import (
    QToolBar,
    QPushButton,
    QLabel,
    QGridLayout,
    QWidget,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap, QDoubleValidator, QIntValidator

from laserstudio.instruments.laser import LaserInstrument
from ...util import resource_path
from typing import TYPE_CHECKING
from ..return_line_edit import ReturnLineEdit

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class LaserToolbar(QToolBar):
    def __init__(self, laser_studio: "LaserStudio", laser_num: int):
        assert laser_num < len(laser_studio.instruments.lasers)
        self.laser: LaserInstrument = laser_studio.instruments.lasers[laser_num]
        super().__init__(f"Laser {laser_num}", laser_studio)
        self.setAllowedAreas(
            Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea
        )
        self.setFloatable(True)
        w = QPushButton(self)
        w.setToolTip("On/Off Laser")
        w.setCheckable(True)
        w.setChecked(False)
        icon = QIcon()
        icon.addPixmap(
            QPixmap(resource_path(":/icons/icons8/lasing.png")),
            QIcon.Mode.Normal,
            QIcon.State.On,
        )
        icon.addPixmap(
            QPixmap(resource_path(":/icons/icons8/not-lasing.png")),
            QIcon.Mode.Normal,
            QIcon.State.Off,
        )
        w.setIcon(icon)
        w.setIconSize(QSize(24, 24))
        w.toggled.connect(lambda b: self.laser.__setattr__("on_off", b))
        self.addWidget(w)

        grid = QGridLayout()
        row = 0

        # Laser pulsed power
        grid.addWidget(QLabel("Pulse power:"), row, 0)
        w = self.pulse_power_input = ReturnLineEdit()
        w.setText("0")
        w.returnPressed.connect(
            lambda: self.laser.__setattr__(
                "current_percentage", float(self.pulse_power_input.text())
            )
        )
        grid.addWidget(w, row, 1)
        grid.addWidget(QLabel("%"), row, 2)
        row += 1

        # Pulse power sweeping
        grid.addWidget(QLabel("Sweep min power:"), row, 0)
        w = self.sweep_min_input = ReturnLineEdit()
        w.setText("0")
        w.setValidator(QDoubleValidator(0.0, 100.0, 2))
        w.returnPressed.connect(
            lambda: self.laser.__setattr__(
                "sweep_min", float(self.sweep_min_input.text())
            )
        )
        grid.addWidget(w, row, 1)
        grid.addWidget(QLabel("%"), row, 2)
        row += 1
        grid.addWidget(QLabel("Sweep max power:"), row, 0)
        w = self.sweep_max_input = ReturnLineEdit()
        w.setText("100")
        w.setValidator(QDoubleValidator(0.0, 100.0, 2))
        w.returnPressed.connect(
            lambda: self.laser.__setattr__(
                "sweep_max", float(self.sweep_max_input.text())
            )
        )
        grid.addWidget(w, row, 1)
        grid.addWidget(QLabel("%"), row, 2)
        row += 1
        grid.addWidget(QLabel("Sweep frequency:"), row, 0)
        w = self.sweep_freq_input = ReturnLineEdit()
        w.setText("10")
        w.setValidator(QIntValidator(1, 10000))
        w.returnPressed.connect(
            lambda: self.laser.__setattr__(
                "sweep_freq", float(self.sweep_freq_input.text())
            )
        )
        grid.addWidget(w, row, 1)
        row += 1

        # Laser test power
        grid.addWidget(QLabel("Offset current:"), row, 0)
        w = self.offset_current_input = ReturnLineEdit()
        w.setValidator(
            QDoubleValidator(0, 150, 3)
        )  # TODO read limit from pypdm if possible
        w.setText("0")
        w.returnPressed.connect(
            lambda: self.laser.__setattr__(
                "offset_current", float(self.offset_current_input.text())
            )
        )
        grid.addWidget(w, row, 1)
        grid.addWidget(QLabel("mA"), row, 2)

        w = QWidget()
        w.setLayout(grid)
        self.addWidget(w)

        self.reload_parameters()

    def reload_parameters(self):
        self.pulse_power_input.setText(f"{self.laser.current_percentage}")
        self.sweep_min_input.setText(f"{self.laser.sweep_min}")
        self.sweep_max_input.setText(f"{self.laser.sweep_max}")
        self.sweep_freq_input.setText(f"{self.laser.sweep_freq}")
        self.offset_current_input.setText(f"{self.laser.offset_current}")
