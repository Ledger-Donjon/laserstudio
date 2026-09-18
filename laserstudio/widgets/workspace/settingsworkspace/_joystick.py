"""Analog joystick toggle(s) for the positioning pad."""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from laserstudio.instruments.stage import StageInstrument
from laserstudio.instruments.stage_pi import PIStageInstrument
from laserstudio.widgets.newui import theme

from ._styles import _JOYSTICK_CAPSULE


class _JoystickControls(QWidget):
    """Analog joystick toggle(s) for the positioning pad."""

    _AXIS_LABELS = "XYZ"

    def __init__(self, stage: StageInstrument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._stage = stage
        # Per-axis control is a PI feature; other stages get a single toggle.
        self._pi = stage if isinstance(stage, PIStageInstrument) else None
        self._updating = False
        self._axis_buttons: list[QPushButton] = []
        self._invert_buttons: list[QPushButton] = []
        self._all_button: QPushButton | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        header = QLabel("Joystick")
        header.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 12px; background: transparent;"
        )
        root.addWidget(header)

        if self._pi is not None:
            hint = QLabel(
                "Enable the analog joystick per axis. Motion commands are rejected "
                "while an axis is under joystick control."
            )
            hint.setWordWrap(True)
            hint.setStyleSheet(
                f"color: {theme.TEXT_DIM}; font-size: 10px; background: transparent;"
            )
            root.addWidget(hint)

            row = QWidget()
            row.setStyleSheet("background: transparent;")
            hbox = QHBoxLayout(row)
            hbox.setContentsMargins(0, 0, 0, 0)
            hbox.setSpacing(6)

            for axis in range(stage.num_axis):
                btn = self._capsule(self._axis_label(axis))
                btn.toggled.connect(
                    lambda checked, ax=axis: self._on_axis_toggled(ax, checked)
                )
                self._axis_buttons.append(btn)
                hbox.addWidget(btn)

            all_btn = self._capsule("ALL")
            all_btn.toggled.connect(self._on_all_toggled)
            self._all_button = all_btn
            hbox.addWidget(all_btn)
            root.addWidget(row)

            invert_header = QLabel("Invert direction")
            invert_header.setStyleSheet(
                f"color: {theme.TEXT_MUTED}; font-size: 12px; background: transparent;"
            )
            invert_header.setToolTip(
                "Reverse the analog joystick travel for each axis. "
                "Useful when pushing the stick up moves the stage down."
            )
            root.addWidget(invert_header)

            invert_row = QWidget()
            invert_row.setStyleSheet("background: transparent;")
            invert_box = QHBoxLayout(invert_row)
            invert_box.setContentsMargins(0, 0, 0, 0)
            invert_box.setSpacing(6)
            for axis in range(stage.num_axis):
                btn = self._capsule(self._axis_label(axis))
                btn.setToolTip(
                    f"Invert joystick motion on the {self._axis_label(axis)} axis"
                )
                btn.toggled.connect(
                    lambda checked, ax=axis: self._on_invert_toggled(ax, checked)
                )
                self._invert_buttons.append(btn)
                invert_box.addWidget(btn)
            root.addWidget(invert_row)
            self._refresh_pi_state()
        else:
            self._toggle = QPushButton("Enable joystick")
            self._toggle.setCheckable(True)
            self._toggle.setStyleSheet(theme.GHOST_BTN)
            self._toggle.setFixedHeight(theme.BTN_MIN_H)
            try:
                from pystages import Corvus

                if isinstance(stage.stage, Corvus):
                    self._toggle.setChecked(stage.stage.joystick_enabled)
            except Exception:
                pass
            self._toggle.toggled.connect(self._on_corvus_toggled)
            root.addWidget(self._toggle)

        # A move turns the joystick off behind the user's back, so the buttons
        # follow the stage rather than only what was last clicked here.
        stage.joystick_changed.connect(self._on_joystick_changed)

    def _on_joystick_changed(self) -> None:
        if self._pi is not None:
            self._refresh_pi_state()
            return
        try:
            from pystages import Corvus

            if isinstance(self._stage.stage, Corvus):
                self._updating = True
                self._toggle.setChecked(self._stage.stage.joystick_enabled)
                self._updating = False
        except Exception as exc:
            self._updating = False
            logging.getLogger("laserstudio").warning(
                "Could not read joystick state: %s", exc
            )

    def _axis_label(self, axis: int) -> str:
        if axis < len(self._AXIS_LABELS):
            return self._AXIS_LABELS[axis]
        return str(axis + 1)

    def _capsule(self, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("ls-joy-capsule")
        btn.setCheckable(True)
        btn.setStyleSheet(_JOYSTICK_CAPSULE)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return btn

    def _refresh_pi_state(self) -> None:
        pi = self._pi
        if pi is None:
            return
        try:
            states = pi.pi_joystick_enabled
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                "Could not read PI joystick state: %s", exc
            )
            return
        inverted: list[bool] = []
        try:
            inverted = pi.pi_joystick_direction_inverted
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                "Could not read PI joystick direction: %s", exc
            )
        self._updating = True
        try:
            for axis, btn in enumerate(self._axis_buttons):
                if axis < len(states):
                    btn.setChecked(states[axis])
            if self._all_button is not None and states:
                self._all_button.setChecked(all(states))
            for axis, btn in enumerate(self._invert_buttons):
                if axis < len(inverted):
                    btn.setChecked(inverted[axis])
        finally:
            self._updating = False

    def _on_axis_toggled(self, axis: int, checked: bool) -> None:
        pi = self._pi
        if self._updating or pi is None:
            return
        try:
            pi.set_pi_joystick_axis(axis, checked)
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                "Failed to set PI joystick on axis %s: %s", axis, exc
            )
            self._refresh_pi_state()
            return
        self._updating = True
        try:
            if self._all_button is not None:
                states = pi.pi_joystick_enabled
                self._all_button.setChecked(all(states))
        finally:
            self._updating = False

    def _on_all_toggled(self, checked: bool) -> None:
        pi = self._pi
        if self._updating or pi is None:
            return
        try:
            pi.pi_joystick_enabled = checked
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                "Failed to set PI joystick on all axes: %s", exc
            )
            self._refresh_pi_state()
            return
        self._refresh_pi_state()

    def _on_invert_toggled(self, axis: int, checked: bool) -> None:
        pi = self._pi
        if self._updating or pi is None:
            return
        try:
            pi.set_pi_joystick_invert_axis(axis, checked)
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                "Failed to invert PI joystick on axis %s: %s", axis, exc
            )
            self._refresh_pi_state()

    def _on_corvus_toggled(self, checked: bool) -> None:
        if self._updating:
            return
        try:
            self._stage.enable_joystick(checked)
        except Exception as exc:
            logging.getLogger("laserstudio").warning(
                "Failed to toggle joystick: %s", exc
            )
            self._updating = True
            self._toggle.setChecked(not checked)
            self._updating = False
