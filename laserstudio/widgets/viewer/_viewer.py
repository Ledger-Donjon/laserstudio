from __future__ import annotations
from PyQt6.QtWidgets import (
    QGraphicsPolygonItem,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsLineItem,
    QWidget,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QPointF, QTimer
from PyQt6.QtGui import (
    QBrush,
    QColorConstants,
    QGuiApplication,
    QPainter,
    QPolygonF,
    QTransform,
    QPen,
    QColor,
)
from typing import Any
import logging
import json
from laserstudio.widgets.stagesight import StageSight
from laserstudio.instruments.probe import ProbeInstrument
from laserstudio.instruments.scans import ScansInstrument, default_zone_color
from laserstudio.instruments.annotations import AnnotationsInstrument
from laserstudio.utils.yaml_types import Config
from laserstudio.utils.colors import LedgerColors
from laserstudio.utils.background_align import BackgroundPin
from laserstudio.utils.util import yaml_to_qtransform, qtransform_to_yaml
from laserstudio.widgets.marker import Marker
from laserstudio.widgets.scangeometry import ScanGeometry
from laserstudio.widgets.softlimits import SoftLimitsItem
from laserstudio.widgets.maxdistance import MaxDistanceItem
from laserstudio.widgets.annotationsgeometry import AnnotationsGeometry
from ._mode import Mode
from ._background import _BackgroundMixin
from ._stage_sight import _StageSightMixin
from ._markers_rulers import _MarkersRulersMixin
from ._navigation import _NavigationMixin


class Viewer(
    _BackgroundMixin,
    _StageSightMixin,
    _MarkersRulersMixin,
    _NavigationMixin,
):
    """
    Widget to display circuit photos, navigate and control position, display the
    results...

    Split across several mixins (see ``_background.py``, ``_stage_sight.py``,
    ``_markers_rulers.py``, ``_navigation.py``) plus this module, which holds
    ``__init__`` and the handful of methods tightly coupled to the Viewer's
    overall mode (``mode``, ``select_mode``, ``__update_selection_color``,
    ...). All of them (and ``QGraphicsView`` itself) ultimately derive from
    ``_ViewerBase`` (``_base.py``), which is what lets each mixin refer to
    state/methods owned by another mixin.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        scans: ScansInstrument | None = None,
        annotations: AnnotationsInstrument | None = None,
    ):
        """
        :param parent: Parent widget.
        """
        super().__init__(parent)

        # # Align objects to the center
        # self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        # The main scene of the graphic view
        self._scene = QGraphicsScene()
        self.setScene(self._scene)

        # Cross cursor
        self.setCursor(Qt.CursorShape.CrossCursor)

        # Make background black
        self.setBackgroundBrush(QBrush(QColorConstants.Black))

        # Selection of mode
        self._mode = Mode.NONE
        self._probe_offset_target: ProbeInstrument | None = None

        # Hide ScrollBars
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Enable anti-aliasing
        self.setRenderHints(QPainter.RenderHint.Antialiasing)

        # Current camera position and zoom factor
        # self.__cam_pos_zoom = QPointF(), 1.0
        self.scale(1, -1)

        # By default, there is no StageSight
        self.stage_sight: StageSight | None = None
        self._follow_stage_sight = False

        # Scan Instrument for the management of scan zones
        self.scans: ScansInstrument = (
            scans if scans is not None else ScansInstrument({})
        )
        self.scan_geometry = ScanGeometry(self.scans)
        self._scene.addItem(self.scan_geometry)
        self.scan_geometry.setZValue(3)

        # Shared rulers and user markers (one model, one graphics layer per viewer).
        self.annotations: AnnotationsInstrument = (
            annotations if annotations is not None else AnnotationsInstrument({})
        )
        self.annotations_geometry = AnnotationsGeometry(self.annotations, self)
        self.annotations.rulers_changed.connect(self.rulers_changed.emit)
        self.annotations.markers_changed.connect(self.markers_changed.emit)

        # Permits to activate tools
        self.setInteractive(True)

        # Augment the scene rect to a very big size.
        self.setSceneRect(-1e6, -1e6, 2e6, 2e6)

        # Background picture
        self._picture_item = None
        self.background_picture_path = None
        self._background_opacity = 1.0
        self._background_base_transform: QTransform | None = None
        self._background_committed_pins: list[BackgroundPin] = []

        # Pin points for background picture
        self.pins: list[tuple[tuple[float, float], tuple[float, float]]] = []
        # PIN Markers
        self.pin_markers = [
            Marker(color=LedgerColors.SerenityPurple.value),
            Marker(color=LedgerColors.SerenityPurple.value),
            Marker(color=LedgerColors.SerenityPurple.value),
        ]
        for m in self.pin_markers:
            m.setZValue(4)
            self._scene.addItem(m)
            m.hide()

        # Ruler being drawn by the user, if any
        self._ruler_in_progress = None

        # To prevent warning, due to QTBUG-103935 (https://bugreports.qt.io/browse/QTBUG-103935)
        if (vp := self.viewport()) is not None:
            vp.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)

        # Polygon for zone creation
        self.zone_poly = QPolygonF()
        self.zone_poly_item = QGraphicsPolygonItem(self.zone_poly)
        self.zone_poly_item.setZValue(2)
        self._scene.addItem(self.zone_poly_item)

        # Offset origin line
        self.offset_origin_line = QGraphicsLineItem()
        self.offset_origin_line.setZValue(10)
        pen = QPen(QColorConstants.White)
        pen.setCosmetic(True)
        self.offset_origin_line.setPen(pen)
        self._scene.addItem(self.offset_origin_line)
        self.offset_origin_line.hide()

        # Software limits box (LaserStudio-side limits, editable in the view)
        self.soft_limits_item = SoftLimitsItem()
        self._scene.addItem(self.soft_limits_item)
        self.soft_limits_item.hide()
        self.soft_limits_item.edit_finished.connect(self._push_soft_limits_to_stage)

        # "Max move distance" guardrail circle, centered on the stage position
        # and editable in the view.
        self.max_distance_item = MaxDistanceItem()
        self._scene.addItem(self.max_distance_item)
        self.max_distance_item.hide()
        self.max_distance_item.edit_finished.connect(self._push_max_distance_to_stage)

        self.setMouseTracking(True)

        # Refit on show/resize until the user zooms with the wheel. Early
        # reset_camera() calls often run before the viewport has its real size.
        self._auto_fit_view = True
        self._camera_fit_pending = False
        self._stage_fit_pending = False
        self.background_changed.connect(self._fit_view_if_auto)

    def _fit_view_if_auto(self) -> None:
        if self._auto_fit_view:
            self.fit_view()

    def schedule_fit_view(self) -> None:
        """Defer fit until after the current layout pass (viewport has real size)."""
        QTimer.singleShot(0, self._fit_view_if_auto)

    def set_auto_fit(self, enabled: bool) -> None:
        """Stop (or resume) the automatic refit done on show and resize.

        Any explicit framing coming from the user — wheel zoom, zoom buttons —
        must turn it off, otherwise the next resize discards their framing.
        """
        self._auto_fit_view = enabled

    def fit_view(self) -> None:
        """Frame the stage sight, or the full scene when a reference image exists."""
        if self.stage_sight is None:
            return
        viewport = self.viewport()
        if viewport is None or viewport.width() < 50 or viewport.height() < 50:
            return
        if self.has_background_picture:
            self.reset_camera()
        else:
            self.reset_camera_to_stage_sight()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if self._auto_fit_view:
            self.schedule_fit_view()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._auto_fit_view:
            self.schedule_fit_view()

    @property
    def mode(self) -> Mode:
        """Mode property to indicate in which mode the Viewer is.

        :return: Current selected mode."""
        return self._mode

    @mode.setter
    def mode(self, new_mode: Mode):
        # Leaving the mode in the middle of a drag must not leave a half-drawn
        # ruler behind.
        if self._ruler_in_progress is not None and new_mode != Mode.RULER:
            self.remove_ruler(self._ruler_in_progress)
            self._ruler_in_progress = None
        if new_mode != Mode.PROBE_OFFSET:
            self._probe_offset_target = None
        self._mode = new_mode
        self._update_drag_mode()
        self.__update_selection_color()
        logging.getLogger("laserstudio").debug(f"Viewer mode selection: {new_mode}")
        self.mode_changed.emit(int(new_mode))

    def select_mode(self, mode: Mode | int, toggle: bool = False):
        """Selects the Viewer's mode. If toggle is set to true,
        the function behaves as 'toggling',
        meaning that the mode is reset to NONE if it is reselected."""

        if toggle and self.mode == mode:
            mode = Mode.NONE

        self.zone_poly.clear()
        self.zone_poly_item.setPolygon(self.zone_poly)

        self.mode = Mode(mode)

    @property
    def probe_offset_target(self) -> ProbeInstrument | None:
        """Probe whose visible position is currently being calibrated."""
        return self._probe_offset_target

    def select_probe_offset(self, probe: ProbeInstrument) -> bool:
        """Wait for one click in the camera image to locate ``probe``.

        Returns false when no camera view is available. Selecting the same
        probe again cancels calibration.
        """
        stage_sight = self.stage_sight
        if stage_sight is None or stage_sight.camera is None:
            return False
        if self.mode == Mode.PROBE_OFFSET and self._probe_offset_target is probe:
            self.select_mode(Mode.NONE)
            return True
        self._probe_offset_target = probe
        self.select_mode(Mode.PROBE_OFFSET)
        return True

    def _set_probe_offset_from_scene(self, scene_pos: QPointF) -> bool:
        """Store a clicked spot position using the ProbeInstrument convention."""
        probe = self._probe_offset_target
        stage_sight = self.stage_sight
        if probe is None or stage_sight is None or stage_sight.camera is None:
            return False

        # StageSight displays sample-plane micrometres (sensor size divided by
        # objective). Probe offsets are stored in sensor-plane micrometres.
        image_pos = stage_sight.image_group.mapFromScene(scene_pos)
        objective = stage_sight.camera.objective
        probe.offset_pos = (
            image_pos.x() * objective,
            image_pos.y() * objective,
        )
        self.select_mode(Mode.NONE)
        return True

    def go_next(self) -> Config:
        """Actions to perform when Laser Studio receive a Go Next command.
        Retrieve the next point position from Scan Geometry
        Inform the StageSight to go to the retrieved position
        """
        result: Config = {}

        if self.stage_sight is not None:
            """Get position of the next point from the shared scan zones"""
            next_point_tuple = self.scans.next_point()

            if next_point_tuple is not None:
                next_point = list(next_point_tuple)
                result = {"next_point_geometry": next_point}

                # Consider the focused element to compute stage's position
                next_point_tuple = self.point_for_desired_move(next_point_tuple)
                result["next_point_applied"] = list(next_point)

                self.stage_sight.move_to(QPointF(*next_point_tuple))
        return result

    def __update_selection_color(self, has_shift: bool | None = None, is_valid: bool = True):
        """Convenience function to change the current Application Palette to modify
        the highlight color. It permits to the Zone creation tool to have green / red
        colors
        """
        if has_shift is None:
            has_shift = (
                Qt.KeyboardModifier.ShiftModifier
                in QGuiApplication.queryKeyboardModifiers()
            )
        if not is_valid:
            # Self-intersecting outline: neither adding nor removing would work.
            base = QColor(QColorConstants.DarkYellow)
        elif has_shift:
            # Subtracting is an erase gesture, so it keeps its own red signal
            # rather than borrowing the zone's color.
            base = QColor(QColorConstants.Red)
        else:
            # Adding: draw in the color of the zone the shape will land in, so
            # it is obvious which zone the gesture targets. With no active
            # zone, preview the color of the one the gesture will create.
            zone = self.scans.active_zone
            base = (
                QColor(zone.color)
                if zone is not None
                else default_zone_color(self.scans.next_zone_id)
            )

        self.setStyleSheet(
            f"QGraphicsView {{ selection-background-color: {base.name()}; }}"
        )
        pen = QPen(base)
        pen.setCosmetic(True)
        fill = QColor(base)
        fill.setAlpha(64)
        self.zone_poly_item.setPen(pen)
        self.zone_poly_item.setBrush(QBrush(fill))

    def _update_selection_color(
        self, has_shift: bool | None = None, is_valid: bool = True
    ) -> None:
        """Mangling-safe entry point for ``__update_selection_color``.

        ``__update_selection_color`` is name-mangled to
        ``_Viewer__update_selection_color`` because it is defined textually in
        this class (some tests call it directly by that mangled name). Code
        living in the mixin modules cannot spell the mangled name, so it goes
        through this normal (unmangled) method instead.
        """
        self.__update_selection_color(has_shift=has_shift, is_valid=is_valid)

    def _update_drag_mode(self):
        if self.mode == Mode.ZONE:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)

    @property
    def settings(self) -> dict[str, Any]:
        """Export settings to a dict for yaml serialization."""
        data: dict[str, Any] = {}

        if self.background_picture_path is not None:
            data["background_picture_path"] = self.background_picture_path
        if (pic := self._picture_item) is not None:
            data["background_picture_transform"] = qtransform_to_yaml(pic.transform())
            data["background_picture_opacity"] = self._background_opacity
            if self._background_committed_pins:
                data["background_alignment_pins"] = [
                    {
                        "image_px": list(pin.image_px),
                        "stage_xy": list(pin.stage_xy),
                    }
                    for pin in self._background_committed_pins
                ]
            data["background_picture_transform_pins"] = [
                [m.pos().x(), m.pos().y()] for m in self.pin_markers
            ]
        return data

    @settings.setter
    def settings(self, data: dict[str, Any]):
        """Import settings from a dict."""
        legacy_annotations: dict[str, Any] = {}
        if (marker_size := data.get("marker_size")) is not None:
            legacy_annotations["marker_size"] = marker_size
        if (rulers := data.get("rulers")) is not None:
            legacy_annotations["rulers"] = rulers
        if legacy_annotations:
            self.annotations.settings = legacy_annotations

        if (path := data.get("background_picture_path")) is not None:
            self.load_picture(path)
            if (opacity := data.get("background_picture_opacity")) is not None:
                self.set_background_opacity(int(round(float(opacity) * 100)))
            if (transform := data.get("background_picture_transform")) is not None and (
                pic := self._picture_item
            ) is not None:
                pic.setTransform(yaml_to_qtransform(transform))
            if (raw_pins := data.get("background_alignment_pins")) is not None:
                committed = [
                    BackgroundPin(
                        image_px=(float(p["image_px"][0]), float(p["image_px"][1])),
                        stage_xy=(float(p["stage_xy"][0]), float(p["stage_xy"][1])),
                    )
                    for p in raw_pins
                ]
                if len(committed) == 3:
                    self._background_committed_pins = committed
                    self.background_changed.emit()
            if (pins := data.get("background_picture_transform_pins")) is not None:
                for i, pin in enumerate(pins):
                    self.pin_markers[i].setPos(pin[0], pin[1])
                    self.pin_markers[i].show()

    def load_markers(self, file_path: str, interactive: bool = False):
        """Load markers from a file."""
        with open(file_path, "r") as f:
            try:
                markers: list[dict[str, Any]] | dict[str, Any] = json.load(f)
            except json.JSONDecodeError:
                QMessageBox.critical(
                    self,
                    "Error loading markers",
                    "The file contains invalid JSON.",
                )
                return
        if isinstance(markers, dict):
            payload = markers.get("markers")
            if isinstance(payload, list):
                markers = payload
            else:
                logging.getLogger("laserstudio").warning(
                    "Marker file is a dict without a 'markers' list."
                )
                return
        if not isinstance(markers, list):
            logging.getLogger("laserstudio").warning(
                f"Marker file has unexpected format: {type(markers)}"
            )
            return

        if interactive:
            # Ask for confirmation
            if not QMessageBox.information(
                self,
                f"{len(markers)} markers loaded",
                f"{len(markers)} markers are ready to be added. Do you want to proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            ):
                return

        self.setUpdatesEnabled(False)
        try:
            added = False
            for marker in markers:
                if not isinstance(marker, dict):
                    continue
                pos = marker.get("pos")
                if not isinstance(pos, list) or len(pos) < 2:
                    logging.getLogger("laserstudio").warning(
                        f"Skipping marker with invalid position: {marker=}"
                    )
                    continue
                raw_color = marker.get("color", [1.0, 0.0, 0.0, 1.0])
                if not isinstance(raw_color, list) or len(raw_color) < 3:
                    raw_color = [1.0, 0.0, 0.0, 1.0]
                if len(raw_color) == 3:
                    raw_color = [*raw_color, 1.0]
                label = marker.get("label")
                visible = not marker.get("hidden", False)
                raw_id = marker.get("id")
                marker_id = (
                    int(raw_id)
                    if isinstance(raw_id, int) and not isinstance(raw_id, bool)
                    else None
                )
                if marker_id is not None and marker_id in self.annotations.markers:
                    marker_id = None
                self.annotations.add_marker(
                    (float(pos[0]), float(pos[1])),
                    raw_color,
                    label=label,
                    visible=visible,
                    marker_id=marker_id,
                    notify=False,
                )
                added = True
            if added:
                # One full view refresh instead of rebuilding the marker tree
                # after every insertion (O(n²) with thousands of markers).
                self.annotations.markers_changed.emit(-1)
        finally:
            self.setUpdatesEnabled(True)

    def save_markers(self, file_path: str):
        """Save markers to a file."""
        with open(file_path, "w") as f:
            json.dump([marker.to_dict() for marker in self.markers], f)
