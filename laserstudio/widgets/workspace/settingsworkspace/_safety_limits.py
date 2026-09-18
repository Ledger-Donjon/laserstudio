"""Stage safety limits: max move distance + stage area (soft limits) guardrails."""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from laserstudio.instruments.stage import StageInstrument
from laserstudio.widgets.newui import theme
from laserstudio.widgets.workspace.schemaform import _INPUT_SS, ToggleSwitch

from ._helpers import _param_grid_cell
from ._styles import _FIELD_CONTROL_H, PANEL_SPACING


class _SafetyLimitsSection(QWidget):
    """Stage safety limits: two independently-toggleable guardrails.

    * **Max move distance**: block any single move whose amplitude exceeds a
      distance (per axis). Maps to :attr:`StageInstrument.guardrail` /
      :attr:`StageInstrument.guardrail_enabled`.
    * **Stage area limit**: confine every move to a rectangular zone, editable
      by dragging the handles of the rectangle in the viewer. Maps to the
      stage software limits (:attr:`StageInstrument.soft_limits_enabled` and the
      soft-limits box).
    """

    def __init__(self, window: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self._stage: StageInstrument = window.instruments.stage
        # Guards against feedback loops while we refresh the widgets from the
        # model (setting a toggle/spin value must not write back to the stage).
        self._updating = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(PANEL_SPACING)

        root.addWidget(theme.section_title("Safety limits", "shield"))

        # ── Max move distance ──────────────────────────────────────────────
        self._distance_toggle = ToggleSwitch(self._stage.guardrail_enabled)
        self._distance_toggle.toggled.connect(self._on_distance_enabled)
        root.addWidget(self._sub_header("Max move distance", self._distance_toggle))
        root.addWidget(self._hint("Block any single move longer than this distance."))
        self._distance_spin = QDoubleSpinBox()
        self._distance_spin.setStyleSheet(_INPUT_SS)
        self._distance_spin.setFixedHeight(_FIELD_CONTROL_H)
        self._distance_spin.setMinimum(0.0)
        self._distance_spin.setMaximum(1_000_000.0)
        self._distance_spin.setDecimals(1)
        self._distance_spin.setSingleStep(1000.0)
        self._distance_spin.setSuffix("\xa0µm")
        self._distance_spin.setValue(self._stage.guardrail)
        self._distance_spin.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._distance_spin.valueChanged.connect(self._on_distance_changed)
        root.addWidget(_param_grid_cell("MAXIMUM DISTANCE", self._distance_spin))

        root.addWidget(theme.separator())

        # ── Stage area limit ───────────────────────────────────────────────
        self._area_toggle = ToggleSwitch(self._stage.soft_limits_enabled)
        self._area_toggle.toggled.connect(self._on_area_enabled)
        root.addWidget(self._sub_header("Stage area limit", self._area_toggle))
        root.addWidget(
            self._hint(
                "Confine every move to a rectangular zone — drag the handles of "
                "the rectangle in the viewer to resize it."
            )
        )
        self._area_bounds = QLabel("—")
        self._area_bounds.setWordWrap(True)
        self._area_bounds.setStyleSheet(
            f"color: {theme.TEXT}; font-family: monospace; font-size: 11px;"
            f" background: {theme.BG_CARD}; border: 1px solid {theme.BORDER};"
            " border-radius: 5px; padding: 8px 10px;"
        )
        self._area_bounds.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        root.addWidget(self._area_bounds)

        self._stage.guardrail_changed.connect(self._refresh_distance)
        self._stage.soft_limits_changed.connect(self._refresh_area)
        self._refresh_distance()
        self._refresh_area()

    # ── construction helpers ───────────────────────────────────────────────
    def _sub_header(self, title: str, toggle: ToggleSwitch) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)
        label = QLabel(title)
        label.setStyleSheet(
            f"color: {theme.TEXT}; font-family: 'Brut Grotesque'; font-weight: 700;"
            " font-size: 13px; background: transparent;"
        )
        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(toggle)
        return row

    def _hint(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; background: transparent;"
        )
        return label

    # ── Max move distance ──────────────────────────────────────────────────
    def _on_distance_enabled(self, on: bool) -> None:
        if self._updating:
            return
        self._stage.guardrail_enabled = on
        viewer = self._window.viewer
        if viewer is not None:
            viewer.set_max_distance_editable(on)

    def _on_distance_changed(self, value: float) -> None:
        if self._updating:
            return
        self._stage.guardrail = float(value)

    def _refresh_distance(self) -> None:
        self._updating = True
        try:
            self._distance_toggle.setChecked(self._stage.guardrail_enabled)
            self._distance_spin.setValue(self._stage.guardrail)
        finally:
            self._updating = False
        viewer = self._window.viewer
        if viewer is not None:
            viewer.set_max_distance_editable(self._stage.guardrail_enabled)

    # ── Stage area limit ───────────────────────────────────────────────────
    def _on_area_enabled(self, on: bool) -> None:
        if self._updating:
            return
        if on and not self._stage.has_soft_limits:
            self._init_default_area()
        self._stage.soft_limits_enabled = on
        viewer = self._window.viewer
        if viewer is not None:
            viewer.set_soft_limits_editable(on)

    def _init_default_area(self) -> None:
        """Create a default area around the visible view / current position."""
        position = self._stage.position.data
        rect = None
        viewer = self._window.viewer
        viewport = viewer.viewport() if viewer is not None else None
        if viewer is not None and viewport is not None:
            rect = viewer.mapToScene(viewport.rect()).boundingRect()
        if rect is not None and rect.width() > 1.0 and rect.height() > 1.0:
            xmin, xmax = rect.left(), rect.right()
            ymin, ymax = rect.top(), rect.bottom()
        else:
            x = position[0] if len(position) > 0 else 0.0
            y = position[1] if len(position) > 1 else 0.0
            xmin, xmax = x - 5000.0, x + 5000.0
            ymin, ymax = y - 5000.0, y + 5000.0
        minimum = [xmin, ymin]
        maximum = [xmax, ymax]
        if self._stage.num_axis >= 3:
            z = position[2] if len(position) > 2 else 0.0
            minimum.append(z - 5000.0)
            maximum.append(z + 5000.0)
        self._stage.set_soft_limits(minimum, maximum)

    def _refresh_area(self) -> None:
        self._updating = True
        try:
            self._area_toggle.setChecked(self._stage.soft_limits_enabled)
            self._area_bounds.setText(self._area_bounds_text())
        finally:
            self._updating = False
        viewer = self._window.viewer
        if viewer is not None:
            viewer.set_soft_limits_editable(self._stage.soft_limits_enabled)

    def _area_bounds_text(self) -> str:
        minimum = self._stage.soft_limits_min
        maximum = self._stage.soft_limits_max
        if minimum is None or maximum is None:
            return "No area defined yet."
        lines = []
        for i, axis in enumerate("XYZ"[: self._stage.num_axis]):
            if i < len(minimum) and i < len(maximum):
                lines.append(f"{axis}: {minimum[i]:g} … {maximum[i]:g} µm")
        return "\n".join(lines) if lines else "No area defined yet."
