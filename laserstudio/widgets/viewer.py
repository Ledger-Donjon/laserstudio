from __future__ import annotations
from PyQt6.QtWidgets import (
    QGraphicsPolygonItem,
    QGraphicsView,
    QGraphicsScene,
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsLineItem,
    QWidget,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColorConstants,
    QWheelEvent,
    QMouseEvent,
    QKeyEvent,
    QGuiApplication,
    QPainter,
    QPixmap,
    QPolygonF,
    QTransform,
    QPen,
    QColor,
)
from enum import Enum, auto
from typing import Any
from shapely import Polygon
import logging
import json
import numpy as np
from .stagesight import (
    StageSight,
    StageInstrument,
    CameraInstrument,
    ProbeInstrument,
    LaserInstrument,
)
from .marker import IdMarker, Marker
from .ruler import Ruler
from .scangeometry import ScanGeometry
from .softlimits import SoftLimitsItem, EDIT_HANDLE_ATTR
from .maxdistance import MaxDistanceItem
from ..instruments.stage import MoveFor, Vector
from ..utils.yaml_types import Config
from ..utils.colors import LedgerColors
from ..utils.background_align import BackgroundPin, compute_affine_transform
from ..utils.util import yaml_to_qtransform, qtransform_to_yaml


class Viewer(QGraphicsView):
    """
    Widget to display circuit photos, navigate and control position, display the
    results...
    """

    class Mode(int, Enum):
        """Viewer modes."""

        NONE = auto()
        STAGE = auto()
        ZONE = auto()
        ZONE_TILTED = auto()
        ZONE_POLY = auto()
        PIN = auto()
        OFFSET_ORIGIN = auto()
        RULER = auto()

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

    # A left click shorter than this distance (in pixels) does not create a
    # ruler, so a misclick in RULER mode does not leave a zero-length item.
    MIN_RULER_DRAG_PIXELS = 5.0

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        # # Align objects to the center
        # self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        # The main scene of the graphic view
        self.__scene = QGraphicsScene()
        self.setScene(self.__scene)

        # Cross cursor
        self.setCursor(Qt.CursorShape.CrossCursor)

        # Make background black
        self.setBackgroundBrush(QBrush(QColorConstants.Black))

        # Selection of mode
        self.__mode = Viewer.Mode.NONE

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

        # Scanning geometry object and its representative item in the view.
        # Also includes the scan path
        self.scan_geometry = ScanGeometry()
        self.__scene.addItem(self.scan_geometry)
        self.scan_geometry.setZValue(3)

        # Permits to activate tools
        self.setInteractive(True)

        # Augment the scene rect to a very big size.
        self.setSceneRect(-1e6, -1e6, 2e6, 2e6)

        # Background picture
        self.__picture_item = None
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
            self.__scene.addItem(m)
            m.hide()

        # Markers
        self.__markers: set[IdMarker] = set()
        self.__markers_by_label_by_color: dict[str | None, dict[str, set[IdMarker]]] = {
            None: {}
        }

        self.default_marker_size = 20.0

        # Rulers (measurement annotations)
        self.__rulers: list[Ruler] = []
        # Appearance applied to the next created ruler
        self.default_ruler_color: QColor = LedgerColors.Grellow.value
        self.default_ruler_graduation: float | None = None
        # Ruler being drawn by the user, if any
        self._ruler_in_progress: Ruler | None = None

        # To prevent warning, due to QTBUG-103935 (https://bugreports.qt.io/browse/QTBUG-103935)
        if (vp := self.viewport()) is not None:
            vp.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)

        # Polygon for zone creation
        self.zone_poly = QPolygonF()
        self.zone_poly_item = QGraphicsPolygonItem(self.zone_poly)
        self.zone_poly_item.setZValue(2)
        self.__scene.addItem(self.zone_poly_item)

        # Offset origin line
        self.offset_origin_line = QGraphicsLineItem()
        self.offset_origin_line.setZValue(10)
        pen = QPen(QColorConstants.White)
        pen.setCosmetic(True)
        self.offset_origin_line.setPen(pen)
        self.__scene.addItem(self.offset_origin_line)
        self.offset_origin_line.hide()

        # Software limits box (LaserStudio-side limits, editable in the view)
        self.soft_limits_item = SoftLimitsItem()
        self.__scene.addItem(self.soft_limits_item)
        self.soft_limits_item.hide()
        self.soft_limits_item.edit_finished.connect(self._push_soft_limits_to_stage)

        # "Max move distance" guardrail circle, centered on the stage position
        # and editable in the view.
        self.max_distance_item = MaxDistanceItem()
        self.__scene.addItem(self.max_distance_item)
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
    def markers(self) -> list[IdMarker]:
        return list(self.__markers)

    @property
    def markers_by_label_by_color(self) -> dict[str | None, dict[str, set[IdMarker]]]:
        return self.__markers_by_label_by_color

    def marker_size(self, value: float):
        self.default_marker_size = value
        self.setUpdatesEnabled(False)
        for m in self.markers:
            m.size = value
        self.setUpdatesEnabled(True)

    @property
    def follow_stage_sight(self) -> bool:
        return self._follow_stage_sight

    @follow_stage_sight.setter
    def follow_stage_sight(self, value: bool):
        """Triggers an update of the camera position when the stage sight change its own position."""
        if self.stage_sight is None:
            return

        # We force to disconnect, in all cases (if already connected).
        if self._follow_stage_sight:
            self.stage_sight.position_changed.disconnect()

        if value:
            self.stage_sight.position_changed.connect(self.__update_cam_pos_zoom)
            self.stage_sight.update_pos()

        # Emit the signal if necessary
        if self._follow_stage_sight != value:
            self._follow_stage_sight = value
            self.follow_stage_sight_changed.emit(value)

    def reset_camera(self, item: QGraphicsPixmapItem | None = None):
        """Resets the camera to show all elements of the scene"""
        if item is not None:
            all_elements_rect = item.sceneTransform().mapRect(item.boundingRect())
            if all_elements_rect.width() <= 0 or all_elements_rect.height() <= 0:
                self.reset_camera_to_stage_sight()
                return
        else:
            all_elements_rect = self.__scene.itemsBoundingRect()
        self._apply_camera_fit(all_elements_rect)

    def _stage_sight_fit_rect(self) -> QRectF | None:
        """Declared camera field of view in scene coordinates (µm)."""
        ss = self.stage_sight
        if ss is None:
            return None
        w, h = float(ss.size.width()), float(ss.size.height())
        if w <= 0 or h <= 0:
            return None
        center = ss.mapToScene(QPointF(0, 0))
        return QRectF(center.x() - w / 2, center.y() - h / 2, w, h)

    def reset_camera_to_stage_sight(self):
        """Resets the camera to show the stage sight field of view."""
        rect = self._stage_sight_fit_rect()
        if rect is None:
            return
        self._apply_camera_fit(rect)

    def _apply_camera_fit(self, all_elements_rect: QRectF) -> None:
        viewport = self.viewport()
        if viewport is None:
            return
        viewport_size = viewport.size()
        if viewport_size.width() < 50 or viewport_size.height() < 50:
            return

        # Scene bounding boxes can be near-zero before the first camera frame
        # (crosshair only), which would yield an extreme zoom factor.
        sight_rect = self._stage_sight_fit_rect()
        if sight_rect is not None:
            min_expected = min(sight_rect.width(), sight_rect.height()) * 0.5
            if (
                all_elements_rect.width() < min_expected
                or all_elements_rect.height() < min_expected
            ):
                all_elements_rect = sight_rect

        w = max(all_elements_rect.width() * 1.2, 1e-9)
        h = max(all_elements_rect.height() * 1.2, 1e-9)
        w_ratio = viewport_size.width() / w
        h_ratio = viewport_size.height() / h
        self.cam_pos_zoom = (
            all_elements_rect.center(),
            min(w_ratio, h_ratio),
        )

    def __place_picture_item(self, at_stage_sight: bool = False):
        item = self.__picture_item
        if item is None:
            return
        # Put if far far away in the back
        item.setZValue(-10)
        if not at_stage_sight or self.stage_sight is None:
            # We place the image at current viewing position
            transform = QTransform()
            pos = (
                self.stage_sight.pos()
                if self.stage_sight is not None and at_stage_sight
                else self.cam_pos_zoom[0]
            )
            transform.translate(pos.x(), pos.y())
            # Scene Y-axis is up, while for images it shall be down. We flip the
            # image over the Y-axis to show it in the right orientation.
            transform.scale(1, -1)
            transform.translate(
                -item.boundingRect().width() / 2, -item.boundingRect().height() / 2
            )
        else:
            # We place the image at current stagesight' position
            transform = self.stage_sight.image.sceneTransform()

        item.setTransform(transform)
        self.__scene.addItem(item)
        item.setOpacity(self._background_opacity)
        self._background_base_transform = QTransform(item.transform())
        self._background_committed_pins.clear()
        self.background_changed.emit()

    def __set_picture_item(self, item: QGraphicsPixmapItem):
        item = self.__picture_item = QGraphicsPixmapItem(item.pixmap())

    def snap_picture_from_camera(self):
        """Takes the current picture from the current
        and set it as background picture"""
        if self.stage_sight is None:
            return
        self.clear_picture()
        self.__set_picture_item(self.stage_sight.image)
        self.__place_picture_item(at_stage_sight=True)

    def clear_picture(self):
        """Clears the background picture"""
        if self.__picture_item is not None:
            self.__scene.removeItem(self.__picture_item)
            self.__picture_item = None
            self.background_picture_path = None
            self._background_base_transform = None
            self._background_committed_pins.clear()
            self.pins.clear()
            for m in self.pin_markers:
                m.hide()
            self.background_changed.emit()

    @property
    def has_background_picture(self) -> bool:
        return self.__picture_item is not None

    @property
    def background_opacity(self) -> int:
        """Opacity percentage (0–100) for the reference image."""
        return int(round(self._background_opacity * 100))

    def set_background_opacity(self, percent: int) -> None:
        self._background_opacity = max(0.0, min(100, percent)) / 100.0
        if self.__picture_item is not None:
            self.__picture_item.setOpacity(self._background_opacity)
        self.background_changed.emit()

    @property
    def background_is_aligned(self) -> bool:
        return len(self._background_committed_pins) == 3

    @property
    def background_committed_pins(self) -> list[BackgroundPin]:
        return list(self._background_committed_pins)

    def background_pixmap(self) -> QPixmap | None:
        if self.__picture_item is None:
            return None
        return self.__picture_item.pixmap()

    def background_picture_transform(self) -> QTransform | None:
        if self.__picture_item is None:
            return None
        return QTransform(self.__picture_item.transform())

    def restore_background_transform(self, transform: QTransform | None) -> None:
        """Restore the background picture transform (e.g. after canceling a preview)."""
        pic = self.__picture_item
        if pic is None:
            return
        if transform is None:
            self._restore_background_base_transform()
            return
        pic.resetTransform()
        pic.setTransform(QTransform(transform))

    def _restore_background_base_transform(self) -> None:
        pic = self.__picture_item
        if pic is None or self._background_base_transform is None:
            return
        pic.resetTransform()
        pic.setTransform(QTransform(self._background_base_transform))

    def preview_background_alignment(self, pins: list[BackgroundPin]) -> bool:
        """Apply a temporary affine transform from *pins* (preview, not committed)."""
        pic = self.__picture_item
        if pic is None:
            return False
        transform = compute_affine_transform(pins)
        if transform is None:
            return False
        pic.resetTransform()
        pic.setTransform(transform)
        return True

    def commit_background_alignment(self, pins: list[BackgroundPin]) -> bool:
        """Persist *pins* and keep the current affine transform."""
        if not self.preview_background_alignment(pins):
            return False
        self._background_committed_pins = list(pins)
        self.pins.clear()
        for m in self.pin_markers:
            m.hide()
        self.background_changed.emit()
        return True

    def reset_background_alignment(self) -> None:
        """Remove alignment distortion; keep image placement and viewer position."""
        self._background_committed_pins.clear()
        self.pins.clear()
        for m in self.pin_markers:
            m.hide()
        self._restore_background_base_transform()
        self.background_changed.emit()

    def background_stage_coords(self) -> tuple[float, float, str]:
        """
        Current stage/scene coordinates for alignment.

        Returns ``(x, y, unit_label)`` where *unit_label* is ``"µm"`` when a
        stage is available, otherwise ``"scene"``.
        """
        if self.stage_sight is None:
            return 0.0, 0.0, "scene"
        if self.stage_sight.stage is not None:
            pos = self.stage_sight.stage.position
            return float(pos[0]), float(pos[1]), "µm"
        scene_pos = self.stage_sight.pos()
        return scene_pos.x(), scene_pos.y(), "scene"

    def capture_background_pin(self, image_px: tuple[float, float]) -> BackgroundPin:
        """Build a pin from an image pixel and the current stage/scene position."""
        stage_xy = self._background_stage_scene_xy()
        return BackgroundPin(image_px=image_px, stage_xy=stage_xy)

    def _background_stage_scene_xy(self) -> tuple[float, float]:
        if self.stage_sight is None:
            return 0.0, 0.0
        if self.stage_sight.stage is None:
            pos = self.stage_sight.pos()
            return pos.x(), pos.y()
        scene = self.stage_sight.scene_coords_from_stage_coords(
            self.stage_sight.stage.position
        )
        return scene.x(), scene.y()

    def load_picture(self, picture_path: str | None = None):
        """Requests loading a backgound picture from the user"""
        if picture_path is not None and len(picture_path):
            filename = picture_path
        else:
            filename = QFileDialog.getOpenFileName(
                self,
                "Open picture",
                "",
                "Images (*.png *.jpg *.jpeg)",
                options=QFileDialog.Option.DontUseNativeDialog,
            )[0]

        if len(filename):
            # Remove previous picture if defined
            self.clear_picture()
            # Get the picture and set it as background
            item = QGraphicsPixmapItem(QPixmap(filename))
            self.__set_picture_item(item)
            self.__place_picture_item()
            # Save picture path for when transform is saved.
            self.background_picture_path = filename

    def add_stage_sight(
        self,
        stage: StageInstrument | None,
        camera: CameraInstrument | None,
        probes: list[ProbeInstrument] = [],
    ):
        """Instantiate a stage sight associated with given stage.

        :param stage: The stage instrument to be associated with the stage sight
        """
        # Add StageSight item
        self.stage_sight = StageSight(stage, camera, probes)
        self.stage_sight.setZValue(1)
        self.__scene.addItem(self.stage_sight)

        self._camera_fit_pending = camera is not None
        if camera is not None:
            camera.new_image.connect(self._on_camera_new_image)
            camera.parameter_changed.connect(self._on_camera_parameter_changed)

        self._stage_fit_pending = stage is not None
        if stage is not None:
            stage.soft_limits_changed.connect(self.refresh_soft_limits_item)
            self.refresh_soft_limits_item()
            stage.guardrail_changed.connect(self.refresh_max_distance_item)
            # Recenter the circle from the stage sight scene position, which does
            # not have the side effect of re-emitting stage.position_changed
            # (reading StageInstrument.position emits that signal).
            self.stage_sight.position_changed.connect(self._on_stage_sight_moved)
            self.refresh_max_distance_item()
            stage.position_changed.connect(self._on_stage_position_for_fit)
            # Place the sight on the first known hardware position before fitting.
            self.stage_sight.update_pos()

        self.schedule_fit_view()

    def _on_stage_position_for_fit(self, _position: Vector) -> None:
        if not self._auto_fit_view or not self._stage_fit_pending:
            return
        self._stage_fit_pending = False
        self.schedule_fit_view()

    def _on_camera_parameter_changed(self, parameter: str, _value: Any) -> None:
        if self._auto_fit_view and parameter in ("objective", "resolution"):
            self.schedule_fit_view()

    def _on_camera_new_image(self, _image: Any) -> None:
        if not self._auto_fit_view or not self._camera_fit_pending:
            return
        self._camera_fit_pending = False
        self.schedule_fit_view()

    def refresh_soft_limits_item(self):
        """Synchronize the soft-limits box in the view with the stage model."""
        stage = self.stage_sight.stage if self.stage_sight is not None else None
        if stage is None:
            return
        minimum = stage.soft_limits_min
        maximum = stage.soft_limits_max
        if minimum is not None and maximum is not None and len(minimum) >= 2:
            self.soft_limits_item.set_bounds(
                minimum[0], minimum[1], maximum[0], maximum[1]
            )

    def set_soft_limits_editable(self, editable: bool):
        """Show or hide the editable soft-limits box in the view."""
        if editable:
            self.refresh_soft_limits_item()
            self.soft_limits_item.show()
        else:
            self.soft_limits_item.hide()

    def _push_soft_limits_to_stage(self, rect: QRectF):
        """Write the XY box edited in the view back to the stage model."""
        stage = self.stage_sight.stage if self.stage_sight is not None else None
        if stage is None:
            return
        stage.set_soft_limits_xy(
            rect.left(), rect.top(), rect.right(), rect.bottom()
        )

    def _on_stage_sight_moved(self, scene_pos: QPointF) -> None:
        """Recenter the max-distance circle on the stage sight scene position."""
        self.max_distance_item.set_center(scene_pos.x(), scene_pos.y())

    def refresh_max_distance_item(self):
        """Synchronize the max-distance circle with the stage guardrail.

        The center is taken from the stage sight scene position to avoid reading
        ``StageInstrument.position`` (which emits ``position_changed``).
        """
        stage = self.stage_sight.stage if self.stage_sight is not None else None
        if stage is None:
            return
        center = self.stage_sight.pos()
        self.max_distance_item.set_center(center.x(), center.y())
        self.max_distance_item.set_radius(stage.guardrail)

    def set_max_distance_editable(self, editable: bool):
        """Show or hide the editable max-distance circle in the view."""
        if editable:
            self.refresh_max_distance_item()
            self.max_distance_item.show()
        else:
            self.max_distance_item.hide()

    def _push_max_distance_to_stage(self, radius: float):
        """Write the radius edited in the view back to the stage guardrail."""
        stage = self.stage_sight.stage if self.stage_sight is not None else None
        if stage is None:
            return
        stage.guardrail = float(radius)

    @property
    def mode(self) -> Mode:
        """Mode property to indicate in which mode the Viewer is.

        :return: Current selected mode."""
        return self.__mode

    @mode.setter
    def mode(self, new_mode: Mode):
        # Leaving the mode in the middle of a drag must not leave a half-drawn
        # ruler behind.
        if self._ruler_in_progress is not None and new_mode != Viewer.Mode.RULER:
            self.remove_ruler(self._ruler_in_progress)
            self._ruler_in_progress = None
        self.__mode = new_mode
        self.__update_drag_mode()
        self.__update_selection_color()
        logging.getLogger("laserstudio").debug(f"Viewer mode selection: {new_mode}")
        self.mode_changed.emit(int(new_mode))

    def select_mode(self, mode: Mode | int, toggle: bool = False):
        """Selects the Viewer's mode. If toogle is set to true,
        the function behaves as 'toggling',
        meaning that the mode is reset to NONE if it is reselected."""

        if toggle and self.mode == mode:
            mode = Viewer.Mode.NONE

        self.zone_poly.clear()
        self.zone_poly_item.setPolygon(self.zone_poly)

        self.mode = Viewer.Mode(mode)

    def go_next(self) -> Config:
        """Actions to perform when Laser Studio receive a Go Next command.
        Retrieve the next point position from Scan Geometry
        Inform the StageSight to go to the retrieved position
        """
        result: Config = {}

        if self.scan_geometry and self.stage_sight is not None:
            """Get position of the next point from the scan geometry"""
            next_point_tuple = self.scan_geometry.next_point()

            if next_point_tuple is not None:
                next_point = list(next_point_tuple)
                result = {"next_point_geometry": next_point}

                # Consider the focused element to compute stage's position
                next_point_tuple = self.point_for_desired_move(next_point_tuple)
                result["next_point_applied"] = list(next_point)

                self.stage_sight.move_to(QPointF(*next_point_tuple))
        return result

    def __update_selection_color(
        self, has_shift: bool | None = None, is_valid: bool = True
    ):
        """Convenience function to change the current Application Palette to modify
        the highlight color. It permits to the Zone creation tool to have green / red
        colors
        """
        if has_shift is None:
            has_shift = (
                Qt.KeyboardModifier.ShiftModifier
                in QGuiApplication.queryKeyboardModifiers()
            )
        color = ("red" if has_shift else "green") if is_valid else "orange"
        self.setStyleSheet(f"QGraphicsView {{ selection-background-color: {color}; }}")
        c = (
            (QColorConstants.Red if has_shift else QColorConstants.Green)
            if is_valid
            else QColorConstants.DarkYellow
        )
        pen = QPen(c)
        if isinstance(c, QColor):
            c.setAlpha(64)
        pen.setCosmetic(True)
        self.zone_poly_item.setPen(pen)
        self.zone_poly_item.setBrush(QBrush(c))

    def __update_drag_mode(self):
        if self.mode == Viewer.Mode.ZONE:
            self.setDragMode(Viewer.DragMode.RubberBandDrag)
        else:
            self.setDragMode(Viewer.DragMode.NoDrag)

    @property
    def cam_pos_zoom(self) -> tuple[QPointF, float]:
        """'Camera' position and zoom of the Viewer: The first element is
        the position in the stage where the viewer is centered on.
        The second element is the zoom factor, which must be strictly positive.

        :return: A tuple containing the point where the viewer is centered
            on and a float indicating the zoom factor.
        """
        return self.__compute_pos_zoom()

    @cam_pos_zoom.setter
    def cam_pos_zoom(self, new_value: tuple[QPointF, float]):
        assert new_value[1] > 0
        self.resetTransform()
        self.scale(new_value[1], -new_value[1])
        self.centerOn(new_value[0])

    @property
    def zoom(self) -> float:
        """Zoom factor of the viewer"""
        return self.cam_pos_zoom[1]

    @zoom.setter
    def zoom(self, factor: float):
        """Change the zoom by applying the zoom factor given in parameter

        :param factor: the zoom factor given in parameter.
        """
        self.cam_pos_zoom = self.cam_pos_zoom[0], factor

    @zoom.deleter
    def zoom(self):
        """Resets the zoom"""
        self.zoom = 1.0

    def __update_cam_pos_zoom(self):
        """Recomputes the camera position according to focused element position and apply it"""
        self.cam_pos_zoom = (self.focused_element_position(), self.zoom)

    # User interactions
    def wheelEvent(self, event: QWheelEvent | None):
        """
        Handle mouse wheel events to manage zoom.
        """
        if event is None:
            return
        self._auto_fit_view = False
        # Get current position and zoom factor of camera
        pos, zoom = self.cam_pos_zoom
        # The zoom factor to apply
        zr = 2 ** (event.angleDelta().y() / (8 * 120))

        if not self._follow_stage_sight:
            # We want to zoom relative to the current cursor position, not relative
            # to the center of the widget. This involves some math...
            # p is the pointed position in the scene, and we want to keep p at the
            # same screen position after changing the zoom. If c1 and c2 are the
            # camera positions before and after the zoom changes,
            # z1 and z2 the zoom levels, then we want:
            # z1 * (p - c1) = z2 * (p - c2)
            # which gives:
            # c2 = c1 * (z1/z2) + p * (1 - z1/z2)
            # we can use zr = z2/z1, the zoom factor to apply.

            # The pointed position
            p = self.mapToScene(event.position().toPoint())
            pos = (pos / zr) + (p * (1 - (1 / zr)))

        zoom *= zr

        # Update the position and zoom factors
        self.cam_pos_zoom = pos, zoom
        event.accept()

    def mousePressEvent(self, event: QMouseEvent | None):
        """
        Called when mouse button is pressed.
        In case of Mode being STAGE, triggers a move of the stage's StageSight.
        In case of Mode being PIN, triggers a pin of the background picture.
        In case of Mode being ZONE_POLY, triggers a polygon shaped zone creation.
        In case of Mode being ZONE_TILTED, triggers a tilted rectangle shaped zone creation.
        In case of Mode being OFFSET_ORIGIN, triggers a line to be drawn from the current position to the mouse position.
        """
        if event is None:
            return

        # Let interactive edit handles (soft-limits box, zone vertices) process
        # their own events, instead of triggering a stage move, a zone creation
        # or any mode-specific action.
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            while item is not None:
                if getattr(item, EDIT_HANDLE_ATTR, False):
                    super().mousePressEvent(event)
                    return
                item = item.parentItem()

        # We want to catch a right-click on a marker or on a ruler, to let their
        # own context menu open instead of starting a pan.
        if event.button() == Qt.MouseButton.RightButton:
            item = self.itemAt(event.pos())
            while item is not None:
                if isinstance(item, (Marker, Ruler)):
                    super().mousePressEvent(event)
                    return
                item = item.parentItem()

        if event.button() == Qt.MouseButton.LeftButton:
            # Map the mouse position to the scene position
            scene_pos = self.mapToScene(event.pos())

            if self.mode == Viewer.Mode.STAGE and self.stage_sight is not None:
                position = (scene_pos.x(), scene_pos.y())
                position = self.point_for_desired_move(position)
                self.stage_sight.move_to(QPointF(*position))
                event.accept()
                return

            if self.mode == Viewer.Mode.PIN:
                self.pin(scene_pos.x(), scene_pos.y())

            elif self.mode == Viewer.Mode.ZONE_TILTED:
                self.zone_poly.append(scene_pos)
                if self.zone_poly.count() == 3:
                    fourth_point = scene_pos - (self.zone_poly[1] - self.zone_poly[0])
                    self.zone_poly.append(fourth_point)
                    if self.is_valid_zone:
                        modifiers = QGuiApplication.queryKeyboardModifiers()
                        if Qt.KeyboardModifier.ShiftModifier in modifiers:
                            self.scan_geometry.remove(self.zone_poly)
                        else:
                            self.scan_geometry.add(self.zone_poly)
                        self.zone_poly.clear()
                        self.zone_poly_item.setPolygon(self.zone_poly)
                    else:
                        self.zone_poly.remove(self.zone_poly.count() - 1)

            elif self.mode == Viewer.Mode.ZONE_POLY:
                self.zone_poly.append(scene_pos)
                self.zone_poly_item.setPolygon(self.zone_poly)

            elif self.mode == Viewer.Mode.OFFSET_ORIGIN:
                self.offset_origin_line.setLine(
                    scene_pos.x(), scene_pos.y(), scene_pos.x(), scene_pos.y()
                )
                self.offset_origin_line.show()

            elif self.mode == Viewer.Mode.RULER:
                self._start_ruler(scene_pos)
                event.accept()
                return

        # The event is a press of the right button
        if event.button() == Qt.MouseButton.RightButton:
            # Disable the StageSight tracking
            self.follow_stage_sight = False

            # Scroll gesture mode
            self.setDragMode(Viewer.DragMode.ScrollHandDrag)

            # Transform as left press button event,
            # to make the scroll by dragging actually effective.
            event = QMouseEvent(
                event.type(),
                event.position(),
                Qt.MouseButton.LeftButton,
                event.buttons(),
                event.modifiers(),
                event.pointingDevice(),
            )

        super().mousePressEvent(event)

    @property
    def is_valid_zone(self) -> bool:
        """
        Check if the zone is valid.
        """
        if self.zone_poly.count() < 3:
            return False
        points = [(p.x(), p.y()) for p in self.zone_poly]
        shapely_poly = Polygon(points)
        return shapely_poly.is_valid

    def mouseMoveEvent(self, event: QMouseEvent | None):
        """
        Called when mouse moves.
        """
        is_valid = True
        if event is not None:
            # Map the mouse position to the scene position
            scene_pos = self.mapToScene(event.pos())
            self.mouse_moved.emit(scene_pos.x(), scene_pos.y())

            # Reveal edit handles only when the cursor is close to them. The
            # threshold is kept constant on screen (in pixels).
            threshold = 24.0 / max(self.zoom, 1e-9)
            if self.soft_limits_item.isVisible():
                self.soft_limits_item.update_cursor_proximity(scene_pos, threshold)
            if self.max_distance_item.isVisible():
                self.max_distance_item.update_cursor_proximity(scene_pos, threshold)
            self.scan_geometry.update_cursor_proximity(scene_pos, threshold)
            for ruler in self.__rulers:
                if ruler is not self._ruler_in_progress:
                    ruler.update_cursor_proximity(scene_pos, threshold)

            if self.mode == Viewer.Mode.ZONE_POLY and not self.zone_poly.isEmpty():
                # Check if mouse button is pressed
                if Qt.MouseButton.LeftButton not in event.buttons():
                    self.zone_poly.remove(self.zone_poly.count() - 1)
                self.zone_poly.append(scene_pos)
                self.zone_poly_item.setPolygon(self.zone_poly)
                is_valid = self.is_valid_zone

            elif self.mode == Viewer.Mode.ZONE_TILTED:
                if (nb_pts := self.zone_poly.count()) == 1:
                    full_poly = QPolygonF(self.zone_poly)
                    full_poly.append(scene_pos)
                    self.zone_poly_item.setPolygon(full_poly)
                elif nb_pts == 2:
                    fourth_point = scene_pos - (self.zone_poly[1] - self.zone_poly[0])
                    full_poly = QPolygonF(self.zone_poly)
                    full_poly.append(scene_pos)
                    full_poly.append(fourth_point)
                    self.zone_poly_item.setPolygon(full_poly)

            elif self.mode == Viewer.Mode.OFFSET_ORIGIN:
                p1 = self.offset_origin_line.line().p1()
                self.offset_origin_line.setLine(
                    p1.x(), p1.y(), scene_pos.x(), scene_pos.y()
                )

            elif self.mode == Viewer.Mode.RULER:
                if (ruler := self._ruler_in_progress) is not None:
                    ruler.set_endpoint(1, scene_pos)

        if self.mode in [
            Viewer.Mode.ZONE,
            Viewer.Mode.ZONE_POLY,
            Viewer.Mode.ZONE_TILTED,
        ]:
            # In Zone Mode, a release of the Shift key makes the highlight
            # color to be changed to red (remove)
            self.__update_selection_color(is_valid=is_valid)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None):
        """
        Called when mouse button is released.
        Used to get out the panning, when Right button is released.
        Used to detect the end of the Zone selection.
        """
        if event is None:
            return
        is_left = event.button() == Qt.MouseButton.LeftButton
        is_right = event.button() == Qt.MouseButton.RightButton

        if is_right:
            # Go back to regular drag mode.
            self.__update_drag_mode()

        if self.mode == Viewer.Mode.ZONE and is_left:
            # Get the corresponding Polygon within the scene
            rect = self.rubberBandRect()
            zone = self.mapToScene(rect)
            # Add or remove the new rectangle to/from the current zone geometry
            modifiers = QGuiApplication.queryKeyboardModifiers()
            if Qt.KeyboardModifier.ShiftModifier in modifiers:
                # Remove the zone to all the polygons
                self.scan_geometry.remove(zone)
            else:
                self.scan_geometry.add(zone)

        elif self.mode == Viewer.Mode.OFFSET_ORIGIN and is_left:
            line = self.offset_origin_line.line()
            offset_p = line.p2() - line.p1()
            offset = [offset_p.x(), offset_p.y()]
            logging.getLogger("laserstudio").debug(f"Offset origin line: {offset}")
            if self.stage_sight is not None and self.stage_sight.stage is not None:
                for i in range(len(offset)):
                    self.stage_sight.stage.offset_origin[i] += offset[i]
            self.offset_origin_line.hide()

        elif self.mode == Viewer.Mode.RULER and is_left:
            self._finish_ruler()

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self.mode == Viewer.Mode.ZONE_POLY:
                self.zone_poly.append(self.mapToScene(event.pos()))
                modifiers = QGuiApplication.queryKeyboardModifiers()
                if Qt.KeyboardModifier.ShiftModifier in modifiers:
                    self.scan_geometry.remove(self.zone_poly)
                else:
                    self.scan_geometry.add(self.zone_poly)
                self.zone_poly_item.setPolygon(QPolygonF())
                self.zone_poly.clear()

        return super().mouseDoubleClickEvent(event)

    def leaveEvent(self, event: Any):
        """Hide the edit handles when the cursor leaves the view."""
        self.soft_limits_item.update_cursor_proximity(None, 0.0)
        self.max_distance_item.update_cursor_proximity(None, 0.0)
        self.scan_geometry.update_cursor_proximity(None, 0.0)
        for ruler in self.__rulers:
            ruler.update_cursor_proximity(None, 0.0)
        super().leaveEvent(event)

    def keyPressEvent(self, event: QKeyEvent | None):
        """
        Called when a keyboard button is pressed.
        """
        if self.mode == Viewer.Mode.ZONE_POLY or self.mode == Viewer.Mode.ZONE:
            self.__update_selection_color(is_valid=True)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent | None):
        """
        Called when a keyboard button is released.
        """
        if self.mode == Viewer.Mode.ZONE_POLY or self.mode == Viewer.Mode.ZONE:
            self.__update_selection_color(is_valid=True)
        super().keyReleaseEvent(event)

    def pin(self, x: float, y: float):
        """
        Called when the user clicks in the viewer, in PIN mode.

        :param x: New position abscissa.
        :param y: New position ordinate.
        """

        if (pic := self.__picture_item) is None:
            return
        if self.stage_sight is None:
            return
        if self.stage_sight.stage is None:
            stage_pos = self.stage_sight.pos()
        else:
            stage_pos = self.stage_sight.scene_coords_from_stage_coords(
                self.stage_sight.stage.position
            )
        stage_pos = stage_pos.x(), stage_pos.y()

        n = len(self.pins)
        if n == 0:
            # We are pinning the first point.
            # Apply simple translation as first step
            tx = stage_pos[0] - x
            ty = stage_pos[1] - y
            t = QTransform()
            t.translate(tx, ty)
            pic.setTransform(pic.sceneTransform() * t)
            x += tx
            y += ty
        # Now pin the point, after initial translation.
        # If we remove the translation code above, the algorithm will still
        # work.
        pix_pos = pic.sceneTransform().inverted()[0].map(x, y)
        pix_pos = (
            pix_pos[0] if pix_pos[0] is not None else 0.0,
            pix_pos[1] if pix_pos[1] is not None else 0.0,
        )

        # Show the marker
        self.pin_markers[n].setPos(x, y)
        for m in self.pin_markers[: n + 1]:
            m.show()
        for m in self.pin_markers[n + 1 :]:
            m.hide()

        self.pins.append((stage_pos, pix_pos))

        logging.getLogger("laserstudio").debug(f"Pins: {self.pins}")
        if len(self.pins) == 3:
            bg_pins = [
                BackgroundPin(image_px=p[1], stage_xy=p[0]) for p in self.pins
            ]
            self.commit_background_alignment(bg_pins)
            self.mode = self.Mode.NONE
        else:
            # Go to stage mode.
            self.mode = self.Mode.STAGE

    def __compute_pos_zoom(self):
        hsb, vsb = self.horizontalScrollBar(), self.verticalScrollBar()
        assert vsb and hsb
        # Get scene positioning in the Viewport thanks to the scrollbars' value
        doc_left = hsb.minimum()
        doc_width = hsb.maximum() + hsb.pageStep() - doc_left
        doc_x = hsb.value() + hsb.pageStep() / 2
        doc_top = vsb.minimum()
        doc_height = vsb.maximum() + vsb.pageStep() - doc_top
        doc_y = vsb.value() + vsb.pageStep() / 2

        # Get scene sizing
        sr = self.sceneRect()

        # Get doc to scene scale factors (invert of zoom)
        scale_x, scale_y = sr.width() / doc_width, sr.height() / doc_height

        # Converts previous positioning
        scene_x = sr.left() + (doc_x - doc_left) * scale_x
        scene_y = sr.bottom() - (doc_y - doc_top) * scale_y

        return QPointF(scene_x, scene_y), 1 / scale_x

    def focused_element_position(self) -> QPointF:
        """
        Gives the focused element's position, indicated by
          self.instruments.stage.move_for.
        """
        stage_sight = self.stage_sight
        if stage_sight is None or stage_sight.stage is None:
            # This should not happen...
            return QPointF()

        pos = stage_sight.mapToScene(0.0, 0.0)
        if stage_sight.stage.move_for.type == MoveFor.Type.CAMERA_CENTER:
            # Camera's center is always placed at StageSigth's coordinates.
            return pos

        if stage_sight.stage.move_for.type == MoveFor.Type.PROBE:
            marker = stage_sight.marker(
                ProbeInstrument, stage_sight.stage.move_for.index
            )
        elif stage_sight.stage.move_for.type == MoveFor.Type.LASER:
            marker = stage_sight.marker(
                LaserInstrument, stage_sight.stage.move_for.index
            )
        else:
            # This should not happen...
            return pos

        if marker is None:
            # This should not happen...
            return pos

        probe_position = stage_sight.mapToScene(marker.pos())
        return probe_position

    def point_for_desired_move(
        self, point: QPointF | tuple[float, float]
    ) -> tuple[float, float]:
        """
        Gives the actual stage's destination according to desired element
          to point at given position, indicated by
          self.instruments.stage.move_for.

        :param point: the desired position.
        :return: the stage's position to apply
        """
        if isinstance(point, QPointF):
            point = point.x(), point.y()

        stage_sight = self.stage_sight
        if stage_sight is None or stage_sight.stage is None:
            # This should not happen...
            return point
        elif stage_sight.stage.move_for.type == MoveFor.Type.CAMERA_CENTER:
            # Camera's center is always placed at Stage's coordinates.
            return point

        # Save camera positioning and zoom
        old_cam_pos_zoom = self.cam_pos_zoom

        # Force a refresh of main stage position (that may change viewer's position)
        stage_position = stage_sight.stage.position.xy.data

        # Get focused element scene's position
        probe_position = self.focused_element_position()

        # Restore the camera position and zoom
        self.cam_pos_zoom = old_cam_pos_zoom

        return (
            point[0] + stage_position[0] - probe_position.x(),
            point[1] + stage_position[1] - probe_position.y(),
        )

    def add_marker(
        self,
        position: None | tuple[float, float] = None,
        color: QColor
        | Qt.GlobalColor
        | int
        | list[float]
        | LedgerColors = QColorConstants.Red,
        label: str | None = None,
        visible: bool = True,
    ) -> IdMarker:
        """
        Add a marker at a specific position, or at current observed position.

        :param position: The position of the marker. If None, the position is retrieved from the stage's current position.
        :param color: The color of the marker.
        :param label: The label of the marker.
        :param visible: If False, the marker is created but not displayed (setVisible(False)).
        :return: The added marker.
        """
        # Creation of the marker
        if position is None:
            p = self.focused_element_position()
            position = p.x(), p.y()

        marker = IdMarker(viewer=self, color=color, label=label, position=position)
        marker.setVisible(visible)
        marker.size = self.default_marker_size

        # Adding to the model
        self.__markers.add(marker)
        if label not in self.__markers_by_label_by_color:
            self.__markers_by_label_by_color[label] = {marker.color_name: set([marker])}
        elif marker.color_name not in self.__markers_by_label_by_color[label]:
            self.__markers_by_label_by_color[label][marker.color_name] = set([marker])
        else:
            self.__markers_by_label_by_color[label][marker.color_name].add(marker)

        # Adding to the view
        self.__scene.addItem(marker)

        return marker

    def clear_markers(self):
        """Removes all markers."""
        for marker in self.__markers:
            self.__scene.removeItem(marker)
            marker.viewer = None
        self.__markers.clear()
        self.__markers_by_label_by_color.clear()

    def remove_marker(self, marker: IdMarker):
        """Remove a specific marker from the scene."""
        self.__scene.removeItem(marker)
        self.__markers.remove(marker)
        self.__markers_by_label_by_color[marker.label][marker.color_name].remove(marker)
        if len(self.__markers_by_label_by_color[marker.label][marker.color_name]) == 0:
            del self.__markers_by_label_by_color[marker.label][marker.color_name]
        if len(self.__markers_by_label_by_color[marker.label]) == 0:
            del self.__markers_by_label_by_color[marker.label]
        logging.getLogger("laserstudio").debug(
            f"Markers by label by color: {self.__markers_by_label_by_color}"
        )
        logging.getLogger("laserstudio").debug(f"Markers: {self.__markers}")
        logging.getLogger("laserstudio").info(f"Marker {marker} removed")
        marker.viewer = None

    # Rulers
    @property
    def rulers(self) -> list[Ruler]:
        return list(self.__rulers)

    def add_ruler(
        self,
        p1: tuple[float, float] | QPointF,
        p2: tuple[float, float] | QPointF,
        color: QColor
        | Qt.GlobalColor
        | int
        | list[float]
        | LedgerColors
        | None = None,
        label: str | None = None,
        graduation: float | None = None,
        graduation_count: float | None = None,
        visible: bool = True,
    ) -> Ruler:
        """
        Add a ruler measuring the distance between two positions.

        :param p1: The position of the first endpoint.
        :param p2: The position of the second endpoint.
        :param color: The color of the ruler. If None, the viewer's default is used.
        :param label: The label of the ruler.
        :param graduation: The graduation interval, in micrometers. If None, the
            ruler is drawn without graduations.
        :param graduation_count: The number of graduations wanted over the whole
            ruler, as an alternative to *graduation*: the ruler keeps that count
            and derives the interval from its length. Ignored when *graduation*
            is given.
        :param visible: If False, the ruler is created but not displayed.
        :return: The added ruler.
        """
        if color is None:
            color = self.default_ruler_color
        if graduation is None and not graduation_count:
            graduation = self.default_ruler_graduation

        ruler = Ruler(
            p1,
            p2,
            viewer=self,
            color=color,
            label=label,
            graduation=graduation,
            graduation_count=graduation_count,
        )
        ruler.setVisible(visible)
        self.__rulers.append(ruler)
        self.__scene.addItem(ruler)
        self.rulers_changed.emit()
        return ruler

    def remove_ruler(self, ruler: Ruler):
        """Remove a specific ruler from the scene."""
        if ruler not in self.__rulers:
            return
        self.__scene.removeItem(ruler)
        self.__rulers.remove(ruler)
        ruler.viewer = None
        logging.getLogger("laserstudio").info(f"Ruler {ruler} removed")
        self.rulers_changed.emit()

    def clear_rulers(self):
        """Remove all rulers."""
        if not self.__rulers:
            return
        for ruler in self.__rulers:
            self.__scene.removeItem(ruler)
            ruler.viewer = None
        self.__rulers.clear()
        self.rulers_changed.emit()

    def _start_ruler(self, scene_pos: QPointF):
        """Begin drawing a ruler; both endpoints start at the same position."""
        self._ruler_in_progress = self.add_ruler(scene_pos, scene_pos)

    def _finish_ruler(self):
        """Commit the ruler being drawn, or discard it if it is too short."""
        ruler = self._ruler_in_progress
        if ruler is None:
            return
        self._ruler_in_progress = None
        if ruler.length * self.zoom < self.MIN_RULER_DRAG_PIXELS:
            self.remove_ruler(ruler)

    @property
    def settings(self) -> dict[str, Any]:
        """Export settings to a dict for yaml serialization."""
        data: dict[str, Any] = {}
        data["marker_size"] = self.default_marker_size
        if self.__rulers:
            data["rulers"] = [ruler.to_dict() for ruler in self.__rulers]

        if self.background_picture_path is not None:
            data["background_picture_path"] = self.background_picture_path
        if (pic := self.__picture_item) is not None:
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
        if (marker_size := data.get("marker_size")) is not None:
            self.marker_size(marker_size)
        if (rulers := data.get("rulers")) is not None:
            self.clear_rulers()
            for ruler in rulers:
                p1, p2 = ruler["p1"], ruler["p2"]
                self.add_ruler(
                    (p1[0], p1[1]),
                    (p2[0], p2[1]),
                    color=ruler.get("color", [1.0, 1.0, 0.0, 1.0]),
                    label=ruler.get("label"),
                    graduation=ruler.get("graduation"),
                    graduation_count=ruler.get("graduation_count"),
                    visible=not ruler.get("hidden", False),
                )
        if (path := data.get("background_picture_path")) is not None:
            self.load_picture(path)
            if (opacity := data.get("background_picture_opacity")) is not None:
                self.set_background_opacity(int(round(float(opacity) * 100)))
            if (transform := data.get("background_picture_transform")) is not None and (
                pic := self.__picture_item
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
                markers: list[dict[str, Any]] = json.load(f)
            except json.JSONDecodeError:
                QMessageBox.critical(
                    self,
                    "Error loading markers",
                    "The file contains invalid JSON.",
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
            for marker in markers:
                color = marker.get("color", [1.0, 0.0, 0.0, 1.0])
                color = QColor(
                    int(color[0] * 255),
                    int(color[1] * 255),
                    int(color[2] * 255),
                    int(color[3] * 255),
                )
                label = marker.get("label", None)
                visible = not marker.get("hidden", False)
                self.add_marker(marker["pos"], color, label=label, visible=visible)
        finally:
            self.setUpdatesEnabled(True)

    def save_markers(self, file_path: str):
        """Save markers to a file."""
        with open(file_path, "w") as f:
            json.dump([marker.to_dict() for marker in self.markers], f)
