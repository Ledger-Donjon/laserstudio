from __future__ import annotations
import logging
from PyQt6.QtWidgets import QGraphicsView
from PyQt6.QtCore import Qt, QPointF, QEvent
from PyQt6.QtGui import (
    QWheelEvent,
    QMouseEvent,
    QKeyEvent,
    QGuiApplication,
    QPolygonF,
    QTransform,
)
from shapely import Polygon
from laserstudio.widgets.marker import Marker
from laserstudio.widgets.ruler import Ruler
from laserstudio.widgets.softlimits import EDIT_HANDLE_ATTR
from laserstudio.instruments.stage import MoveFor
from laserstudio.instruments.probe import ProbeInstrument
from laserstudio.instruments.laser import LaserInstrument
from laserstudio.utils.background_align import BackgroundPin
from ._mode import Mode
from ._base import _ViewerBase


class _NavigationMixin(_ViewerBase):
    """Camera positioning/zoom and mouse/keyboard interaction: panning,
    zooming, and all mode-specific gestures (stage move, zones, pins,
    rulers, offset origin)."""

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
            self.stage_sight.position_changed.connect(self._update_cam_pos_zoom)
            self.stage_sight.update_pos()

        # Emit the signal if necessary
        if self._follow_stage_sight != value:
            self._follow_stage_sight = value
            self.follow_stage_sight_changed.emit(value)

    @property
    def cam_pos_zoom(self) -> tuple[QPointF, float]:
        """'Camera' position and zoom of the Viewer: The first element is
        the position in the stage where the viewer is centered on.
        The second element is the zoom factor, which must be strictly positive.

        :return: A tuple containing the point where the viewer is centered
            on and a float indicating the zoom factor.
        """
        return self._compute_pos_zoom()

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

    def _update_cam_pos_zoom(self):
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

            if self.mode == Mode.STAGE and self.stage_sight is not None:
                position = (scene_pos.x(), scene_pos.y())
                position = self.point_for_desired_move(position)
                self.stage_sight.move_to(QPointF(*position))
                event.accept()
                return

            if self.mode == Mode.PIN:
                self.pin(scene_pos.x(), scene_pos.y())

            elif self.mode == Mode.MARKER:
                self.add_marker((scene_pos.x(), scene_pos.y()))
                event.accept()
                return

            elif self.mode == Mode.PROBE_OFFSET:
                if self._set_probe_offset_from_scene(scene_pos):
                    event.accept()
                    return

            elif self.mode == Mode.ZONE_TILTED:
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

            elif self.mode == Mode.ZONE_POLY:
                self.zone_poly.append(scene_pos)
                self.zone_poly_item.setPolygon(self.zone_poly)

            elif self.mode == Mode.OFFSET_ORIGIN:
                self.offset_origin_line.setLine(
                    scene_pos.x(), scene_pos.y(), scene_pos.x(), scene_pos.y()
                )
                self.offset_origin_line.show()

            elif self.mode == Mode.RULER:
                self._start_ruler(scene_pos)
                event.accept()
                return

        # The event is a press of the right button
        if event.button() == Qt.MouseButton.RightButton:
            # Disable the StageSight tracking
            self.follow_stage_sight = False

            # Scroll gesture mode
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

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
        points = [
            (self.zone_poly[i].x(), self.zone_poly[i].y())
            for i in range(self.zone_poly.count())
        ]
        shapely_poly = Polygon(points)
        return bool(shapely_poly.is_valid)

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
            for ruler in self.rulers:
                if ruler is not self._ruler_in_progress:
                    ruler.update_cursor_proximity(scene_pos, threshold)

            if self.mode == Mode.ZONE_POLY and not self.zone_poly.isEmpty():
                # Check if mouse button is pressed
                if Qt.MouseButton.LeftButton not in event.buttons():
                    self.zone_poly.remove(self.zone_poly.count() - 1)
                self.zone_poly.append(scene_pos)
                self.zone_poly_item.setPolygon(self.zone_poly)
                is_valid = self.is_valid_zone

            elif self.mode == Mode.ZONE_TILTED:
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

            elif self.mode == Mode.OFFSET_ORIGIN:
                p1 = self.offset_origin_line.line().p1()
                self.offset_origin_line.setLine(
                    p1.x(), p1.y(), scene_pos.x(), scene_pos.y()
                )

            elif self.mode == Mode.RULER:
                if (in_progress_ruler := self._ruler_in_progress) is not None:
                    in_progress_ruler.set_endpoint(1, scene_pos)

        if self.mode in [
            Mode.ZONE,
            Mode.ZONE_POLY,
            Mode.ZONE_TILTED,
        ]:
            # In Zone Mode, a release of the Shift key makes the highlight
            # color to be changed to red (remove)
            self._update_selection_color(is_valid=is_valid)

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
            self._update_drag_mode()

        if self.mode == Mode.ZONE and is_left:
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

        elif self.mode == Mode.OFFSET_ORIGIN and is_left:
            line = self.offset_origin_line.line()
            offset_p = line.p2() - line.p1()
            offset = [offset_p.x(), offset_p.y()]
            logging.getLogger("laserstudio").debug(f"Offset origin line: {offset}")
            if self.stage_sight is not None and self.stage_sight.stage is not None:
                for i in range(len(offset)):
                    self.stage_sight.stage.offset_origin[i] += offset[i]
            self.offset_origin_line.hide()

        elif self.mode == Mode.RULER and is_left:
            self._finish_ruler()

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self.mode == Mode.ZONE_POLY:
                self.zone_poly.append(self.mapToScene(event.pos()))
                modifiers = QGuiApplication.queryKeyboardModifiers()
                if Qt.KeyboardModifier.ShiftModifier in modifiers:
                    self.scan_geometry.remove(self.zone_poly)
                else:
                    self.scan_geometry.add(self.zone_poly)
                self.zone_poly_item.setPolygon(QPolygonF())
                self.zone_poly.clear()

        return super().mouseDoubleClickEvent(event)

    def leaveEvent(self, a0: QEvent | None):
        """Hide the edit handles when the cursor leaves the view."""
        self.soft_limits_item.update_cursor_proximity(None, 0.0)
        self.max_distance_item.update_cursor_proximity(None, 0.0)
        self.scan_geometry.update_cursor_proximity(None, 0.0)
        for ruler in self.rulers:
            ruler.update_cursor_proximity(None, 0.0)
        super().leaveEvent(a0)

    def keyPressEvent(self, event: QKeyEvent | None):
        """
        Called when a keyboard button is pressed.
        """
        if self.mode == Mode.ZONE_POLY or self.mode == Mode.ZONE:
            self._update_selection_color(is_valid=True)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent | None):
        """
        Called when a keyboard button is released.
        """
        if self.mode == Mode.ZONE_POLY or self.mode == Mode.ZONE:
            self._update_selection_color(is_valid=True)
        super().keyReleaseEvent(event)

    def pin(self, x: float, y: float):
        """
        Called when the user clicks in the viewer, in PIN mode.

        :param x: New position abscissa.
        :param y: New position ordinate.
        """

        if (pic := self._picture_item) is None:
            return
        stage_sight = self.stage_sight
        if stage_sight is None:
            return
        if stage_sight.stage is None:
            stage_point = stage_sight.pos()
        else:
            stage_point = stage_sight.scene_coords_from_stage_coords(
                stage_sight.stage.position
            )
        stage_pos = stage_point.x(), stage_point.y()

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
            bg_pins = [BackgroundPin(image_px=p[1], stage_xy=p[0]) for p in self.pins]
            self.commit_background_alignment(bg_pins)
            self.mode = Mode.NONE
        else:
            # Go to stage mode.
            self.mode = Mode.STAGE

    def _compute_pos_zoom(self) -> tuple[QPointF, float]:
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
