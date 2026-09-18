"""One-click probe-offset calibration + the generic (non-laser) probe section."""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from laserstudio.instruments.probe import ProbeInstrument
from laserstudio.widgets.newui import lucide, theme
from laserstudio.widgets.viewer import Viewer

from ._styles import _MONO_DIM, _MONO_MUTED, PANEL_SPACING


class _ProbeOffsetControl(QWidget):
    """One-click calibration of a probe's visible position in the main viewer."""

    def __init__(
        self,
        probe: ProbeInstrument,
        viewer: Viewer | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._probe = probe
        self._viewer = viewer

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(7)

        header = QHBoxLayout()
        label = QLabel("PROBE OFFSET")
        label.setStyleSheet(_MONO_MUTED)
        header.addWidget(label)
        header.addStretch()
        self._value = QLabel()
        self._value.setStyleSheet(_MONO_DIM)
        header.addWidget(self._value)
        root.addLayout(header)

        self._button = QPushButton("Select spot in viewer")
        self._button.setCheckable(True)
        self._button.setIcon(lucide.icon("crosshair", 15, theme.TEXT))
        self._button.setToolTip(
            "Click, then select in the viewer where this probe or laser spot appears."
        )
        available = (
            viewer is not None
            and viewer.stage_sight is not None
            and viewer.stage_sight.camera is not None
        )
        self._button.setEnabled(available)
        if not available:
            self._button.setToolTip("A camera view is required to set the probe offset.")
        self._button.clicked.connect(self._select_in_viewer)
        root.addWidget(self._button)

        hint = QLabel(
            "The selected point is measured relative to the centre of the camera image."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; background: transparent;"
        )
        root.addWidget(hint)

        probe.offset_pos_changed.connect(self._refresh)
        if viewer is not None:
            viewer.mode_changed.connect(self._on_viewer_mode_changed)
        self._refresh()

    def _select_in_viewer(self) -> None:
        viewer = self._viewer
        if viewer is None or not viewer.select_probe_offset(self._probe):
            self._sync_button(False)

    def _on_viewer_mode_changed(self, mode_id: int) -> None:
        viewer = self._viewer
        active = (
            viewer is not None
            and mode_id == int(Viewer.Mode.PROBE_OFFSET)
            and viewer.probe_offset_target is self._probe
        )
        self._sync_button(active)

    def _sync_button(self, active: bool) -> None:
        self._button.blockSignals(True)
        self._button.setChecked(active)
        self._button.setText(
            "Click the spot in the viewer…" if active else "Select spot in viewer"
        )
        self._button.setIcon(
            lucide.icon("crosshair", 15, theme.PURPLE if active else theme.TEXT)
        )
        self._button.blockSignals(False)

    def _refresh(self) -> None:
        offset = self._probe.offset_pos
        self._value.setText(
            "NOT SET"
            if offset is None
            else f"X {offset[0]:+.2f}  Y {offset[1]:+.2f} µm"
        )


class _ProbeSection(QWidget):
    """Settings section for a generic (non-laser) probe."""

    def __init__(
        self,
        probe: ProbeInstrument,
        index: int,
        viewer: Viewer | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(PANEL_SPACING)

        title = QLabel(probe.label or f"Probe {index + 1}")
        title.setStyleSheet(
            f"color: {theme.TEXT}; font-family: 'Brut Grotesque'; font-weight: 700;"
            " font-size: 15px; background: transparent;"
        )
        root.addWidget(title)
        root.addWidget(_ProbeOffsetControl(probe, viewer))
