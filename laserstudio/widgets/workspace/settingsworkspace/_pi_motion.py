"""Closed-loop VEL/ACC/DEC controls for PI/Mercury stages."""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from laserstudio.instruments.stage_pi import PIStageInstrument
from laserstudio.widgets.newui import theme

from ._helpers import _FloatSliderRow
from ._styles import PANEL_SPACING


class _PIMotionSection(QWidget):
    """Closed-loop VEL/ACC/DEC controls for PI/Mercury stages."""

    _AXIS_LABELS = "XYZ"

    def __init__(self, stage: PIStageInstrument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._stage = stage
        self._updating = False
        self._velocity_sliders: list[_FloatSliderRow] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(PANEL_SPACING)

        root.addWidget(theme.section_title("PI motion", "move-3d"))
        hint = QLabel(
            "Closed-loop velocity, acceleration and deceleration for each Mercury "
            "controller axis (mm/s and mm/s²). Also applies under joystick control."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; background: transparent;"
        )
        root.addWidget(hint)

        try:
            velocity = stage.pi_velocity_mm_s
            acceleration = stage.pi_acceleration_mm_s2
            deceleration = stage.pi_deceleration_mm_s2
            velocity_max = stage.pi_velocity_max_mm_s
            acceleration_max = stage.pi_acceleration_max_mm_s2
            deceleration_max = stage.pi_deceleration_max_mm_s2
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                "Could not read PI motion parameters: %s", exc
            )
            error = QLabel("Unable to read PI motion parameters from the controller.")
            error.setWordWrap(True)
            error.setStyleSheet(
                f"color: {theme.ACCENT}; font-size: 11px; background: transparent;"
            )
            root.addWidget(error)
            return

        for axis in range(stage.num_axis):
            axis_label = (
                self._AXIS_LABELS[axis] if axis < len(self._AXIS_LABELS) else str(axis + 1)
            )
            title = QLabel(f"Axis {axis_label}")
            title.setStyleSheet(
                f"color: {theme.TEXT}; font-family: 'Brut Grotesque'; font-weight: 700;"
                " font-size: 12px; background: transparent;"
            )
            root.addWidget(title)

            vel_max = max(0.001, velocity_max[axis])
            acc_max = max(0.1, acceleration_max[axis])
            dec_max = max(0.1, deceleration_max[axis])

            vel_slider = _FloatSliderRow(
                "VELOCITY",
                0.0,
                vel_max,
                min(vel_max, velocity[axis]),
                scale=1000,
                suffix="\xa0mm/s",
                decimals=3,
                on_change=lambda value, ax=axis: self._on_velocity_changed(ax, value),
            )
            acc_slider = _FloatSliderRow(
                "ACCELERATION",
                0.0,
                acc_max,
                min(acc_max, acceleration[axis]),
                scale=10,
                suffix="\xa0mm/s²",
                decimals=1,
                on_change=lambda value, ax=axis: self._on_acceleration_changed(ax, value),
            )
            dec_slider = _FloatSliderRow(
                "DECELERATION",
                0.0,
                dec_max,
                min(dec_max, deceleration[axis]),
                scale=10,
                suffix="\xa0mm/s²",
                decimals=1,
                on_change=lambda value, ax=axis: self._on_deceleration_changed(ax, value),
            )
            root.addWidget(vel_slider)
            root.addWidget(acc_slider)
            root.addWidget(dec_slider)
            self._velocity_sliders.append(vel_slider)

            if axis < stage.num_axis - 1:
                root.addWidget(theme.separator())

        # The joystick buttons change the speed for good, so the sliders have
        # to follow the stage and not only what was last dragged here.
        stage.velocity_changed.connect(self._refresh_velocity_sliders)

    def _refresh_velocity_sliders(self) -> None:
        try:
            velocities = self._stage.pi_velocity_mm_s
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                "Could not read PI velocity: %s", exc
            )
            return
        self._updating = True
        try:
            for slider, velocity in zip(self._velocity_sliders, velocities):
                slider.set_value(velocity)
        finally:
            self._updating = False

    def _on_velocity_changed(self, axis: int, value: float) -> None:
        if self._updating:
            return
        self._stage.set_pi_axis_motion(axis, velocity_mm_s=float(value))

    def _on_acceleration_changed(self, axis: int, value: float) -> None:
        if self._updating:
            return
        self._stage.set_pi_axis_motion(axis, acceleration_mm_s2=float(value))

    def _on_deceleration_changed(self, axis: int, value: float) -> None:
        if self._updating:
            return
        self._stage.set_pi_axis_motion(axis, deceleration_mm_s2=float(value))
