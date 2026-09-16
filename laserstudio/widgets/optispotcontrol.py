import logging
import math

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QPushButton,
    QSlider,
    QWidget,
)

from ..instruments.stage import StageInstrument, Vector

OPTISPOT_MIN = 0
OPTISPOT_MAX = 1500  # 1.5mm
OPTISPOT_STEP = 1


class OptispotControl(QWidget):
    """Slider, +/- buttons and a numeric field driving a laser's optispot axis."""

    def __init__(self, optispot: StageInstrument, parent: QWidget | None = None):
        """
        :param optispot: Single-axis stage to be controlled by the widget.
        """
        super().__init__(parent)
        self.optispot = optispot
        # Base for the +/- buttons: the last position the stage reported.
        self.last_position = float(OPTISPOT_MIN)

        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        self.setLayout(hbox)

        w = QPushButton("-")
        w.setToolTip("Decrease optispot position")
        w.setFixedWidth(28)
        w.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        w.clicked.connect(lambda: self.move_by(-OPTISPOT_STEP))
        hbox.addWidget(w)

        w = self.slider = QSlider(Qt.Orientation.Horizontal, self)
        w.setRange(OPTISPOT_MIN, OPTISPOT_MAX)
        w.setSingleStep(OPTISPOT_STEP)
        w.setToolTip("Position of the optispot")
        w.valueChanged.connect(lambda v: self.move_to(float(v)))
        hbox.addWidget(w)

        w = QPushButton("+")
        w.setToolTip("Increase optispot position")
        w.setFixedWidth(28)
        w.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        w.clicked.connect(lambda: self.move_by(OPTISPOT_STEP))
        hbox.addWidget(w)

        w = self.position_input = QDoubleSpinBox()
        w.setMinimum(float(OPTISPOT_MIN))
        w.setMaximum(float(OPTISPOT_MAX))
        w.setDecimals(1)
        w.setSingleStep(float(OPTISPOT_STEP))
        # Without this, typing '250' would move to 2, then 25, then 250.
        w.setKeyboardTracking(False)
        w.setToolTip("Position of the optispot")
        w.setSuffix(" µm")
        w.valueChanged.connect(self.move_to)
        hbox.addWidget(w)

        optispot.position_changed.connect(self.update_position)
        try:
            self.update_position(optispot.position)
        except Exception as e:
            logging.getLogger("laserstudio").warning(
                f"Failed to read the optispot position: {e!s}"
            )

    def update_position(self, position: Vector):
        """Refresh the widgets from a position reported by the stage."""
        x = float(position.x)
        if math.isnan(x):
            # An unreadable position must not become the base for +/-.
            return
        self.last_position = x
        value = max(float(OPTISPOT_MIN), min(float(OPTISPOT_MAX), x))

        line_edit = self.position_input.lineEdit()
        if line_edit is None or not line_edit.hasFocus():
            self.position_input.blockSignals(True)
            self.position_input.setValue(value)
            self.position_input.blockSignals(False)

        if not self.slider.isSliderDown():
            self.slider.blockSignals(True)
            self.slider.setValue(round(value))
            self.slider.blockSignals(False)

    def move_by(self, displacement: float):
        self.move_to(self.last_position + displacement)

    def move_to(self, value: float):
        value = max(float(OPTISPOT_MIN), min(float(OPTISPOT_MAX), value))
        try:
            self.optispot.move_to(Vector(value), wait=False)
        except Exception as e:
            logging.getLogger("laserstudio").warning(
                f"Failed to move the optispot: {e!s}"
            )
