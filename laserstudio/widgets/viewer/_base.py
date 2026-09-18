from __future__ import annotations
from typing import TypeAlias
from PyQt6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsLineItem,
)
from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtGui import QTransform, QPolygonF, QColor
from laserstudio.widgets.stagesight import StageSight
from laserstudio.widgets.marker import Marker, IdMarker
from laserstudio.widgets.ruler import Ruler
from laserstudio.widgets.scangeometry import ScanGeometry
from laserstudio.widgets.softlimits import SoftLimitsItem
from laserstudio.widgets.maxdistance import MaxDistanceItem
from laserstudio.widgets.annotationsgeometry import AnnotationsGeometry
from laserstudio.instruments.scans import ScansInstrument
from laserstudio.instruments.annotations import AnnotationsInstrument
from laserstudio.instruments.probe import ProbeInstrument
from laserstudio.utils.background_align import BackgroundPin
from laserstudio.utils.colors import LedgerColors
from ._mode import Mode


class _ViewerBase(QGraphicsView):
    """Common ground for every Viewer mixin.

    ``Viewer`` (in ``_viewer.py``) is split across several mixins
    (``_BackgroundMixin``, ``_StageSightMixin``, ``_MarkersRulersMixin``,
    ``_NavigationMixin``), each implementing one themed slice of behaviour,
    but they all operate on the same instance state, set up once in
    ``Viewer.__init__``. This base class is what lets a mixin refer to
    attributes/methods owned by *another* mixin (or by ``Viewer`` itself)
    without the mixins importing each other (which would be circular) or
    duplicating logic:

    - Instance attributes are declared here as type annotations only (no
      assignment); the real values are all assigned exactly once, in
      ``Viewer.__init__``.
    - Cross-mixin methods/properties are declared here with a
      ``raise NotImplementedError`` body; the concrete mixin providing the
      real implementation appears earlier in ``Viewer``'s MRO, so it is
      always what actually runs.

    None of this changes runtime behaviour: it only lets each mixin module
    be type-checked on its own.
    """

    # -- Signals (identical to the ones on the original, single-file Viewer) --
    # Signal emitted when a new mode is set
    mode_changed = pyqtSignal(int)
    # Signal emitted when the mouse has moved in scene
    mouse_moved = pyqtSignal(float, float)
    # Signal emitted when the follow stage sight option changed
    follow_stage_sight_changed = pyqtSignal(bool)
    # Background reference image state
    background_changed = pyqtSignal()
    # Signal emitted when a ruler is added or removed
    rulers_changed = pyqtSignal()
    # Signal emitted when a marker is added, removed or updated in the model
    markers_changed = pyqtSignal()

    # A left click shorter than this distance (in pixels) does not create a
    # ruler, so a misclick in RULER mode does not leave a zero-length item.
    MIN_RULER_DRAG_PIXELS = 5.0

    # Exposed for backward compatibility: external code refers to it as
    # ``Viewer.Mode`` (or an instance's ``.Mode``). The enum itself lives at
    # module level (``_mode.py``) so every mixin module can import and use it
    # without risking a circular import with ``_viewer.py``.
    Mode: TypeAlias = Mode

    # -- Shared instance state (assigned in Viewer.__init__) --
    _scene: QGraphicsScene
    _mode: Mode
    _probe_offset_target: ProbeInstrument | None
    stage_sight: StageSight | None
    _follow_stage_sight: bool
    scans: ScansInstrument
    scan_geometry: ScanGeometry
    annotations: AnnotationsInstrument
    annotations_geometry: AnnotationsGeometry
    _picture_item: QGraphicsPixmapItem | None
    background_picture_path: str | None
    _background_opacity: float
    _background_base_transform: QTransform | None
    _background_committed_pins: list[BackgroundPin]
    pins: list[tuple[tuple[float, float], tuple[float, float]]]
    pin_markers: list[Marker]
    _ruler_in_progress: Ruler | None
    zone_poly: QPolygonF
    zone_poly_item: QGraphicsPolygonItem
    offset_origin_line: QGraphicsLineItem
    soft_limits_item: SoftLimitsItem
    max_distance_item: MaxDistanceItem
    _auto_fit_view: bool
    _camera_fit_pending: bool
    _stage_fit_pending: bool

    # -- Cross-mixin properties --
    # (Real implementation: _NavigationMixin)
    @property
    def cam_pos_zoom(self) -> tuple[QPointF, float]:
        raise NotImplementedError

    @cam_pos_zoom.setter
    def cam_pos_zoom(self, new_value: tuple[QPointF, float]) -> None:
        raise NotImplementedError

    @property
    def zoom(self) -> float:
        raise NotImplementedError

    @zoom.setter
    def zoom(self, factor: float) -> None:
        raise NotImplementedError

    # (Real implementation: _MarkersRulersMixin)
    @property
    def rulers(self) -> list[Ruler]:
        raise NotImplementedError

    # (Real implementation: Viewer, in _viewer.py)
    @property
    def mode(self) -> Mode:
        raise NotImplementedError

    @mode.setter
    def mode(self, new_mode: Mode) -> None:
        raise NotImplementedError

    # -- Cross-mixin / cross-module methods --
    # (Real implementation: _NavigationMixin)
    def focused_element_position(self) -> QPointF:
        raise NotImplementedError

    # (Real implementation: _MarkersRulersMixin)
    def add_marker(
        self,
        position: None | tuple[float, float] | list[float] = None,
        color: QColor | Qt.GlobalColor | int | list[float] | LedgerColors | None = None,
        label: str | None = None,
        visible: bool = True,
        *,
        marker_id: int | None = None,
    ) -> IdMarker:
        raise NotImplementedError

    def _start_ruler(self, scene_pos: QPointF) -> None:
        raise NotImplementedError

    def _finish_ruler(self) -> None:
        raise NotImplementedError

    # (Real implementation: _BackgroundMixin)
    def commit_background_alignment(self, pins: list[BackgroundPin]) -> bool:
        raise NotImplementedError

    # (Real implementation: Viewer, in _viewer.py)
    def schedule_fit_view(self) -> None:
        raise NotImplementedError

    def _set_probe_offset_from_scene(self, scene_pos: QPointF) -> bool:
        raise NotImplementedError

    def _update_selection_color(
        self, has_shift: bool | None = None, is_valid: bool = True
    ) -> None:
        raise NotImplementedError

    def _update_drag_mode(self) -> None:
        raise NotImplementedError
