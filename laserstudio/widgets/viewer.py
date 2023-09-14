from PyQt6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
)
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import (
    QBrush,
    QColorConstants,
    QWheelEvent,
    QMouseEvent,
    QKeyEvent,
    QGuiApplication,
    QPalette,
    QPainter,
)
from enum import IntEnum, auto
from typing import Optional, Tuple
from .stagesight import StageSight, StageInstrument, CameraInstrument
import logging
from .scangeometry import ScanGeometry


class Viewer(QGraphicsView):
    """
    Widget to display circuit photos, navigate and control position, display the
    results...
    """

    class Mode(IntEnum):
        """Viewer modes."""

        NONE = auto()
        STAGE = auto()
        ZONE = auto()

    def __init__(self, parent=None):
        super().__init__(parent)

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
        self.__cam_pos_zoom = QPointF(), 1.0
        self.scale(1, -1)

        # By default, there is no StageSight
        self.stage_sight = None

        # Scanning geometry object and its representative item in the view.
        # Also includes the scan path
        self.scan_geometry = ScanGeometry()
        self.__scene.addItem(self.scan_geometry)
        self.scan_geometry.setZValue(3)

        # Permits to activate tools
        self.setInteractive(True)

        # Augment the scene rect to a very big size.
        self.setSceneRect(-1e6, -1e6, 2e6, 2e6)

        self._default_highlight_color = QGuiApplication.palette().color(
            QPalette.ColorRole.Highlight
        )

    def follow_stagesight(self, value: bool):
        if self.stage_sight is None or self.stage_sight.stage is None:
            return
        try:
            self.stage_sight.position_changed.disconnect()
        except:
            pass

        if value:
            self.stage_sight.position_changed.connect(
                lambda pos: self.__setattr__(
                    "cam_pos_zoom", (pos, self.cam_pos_zoom[1])
                )
            )

    def reset_camera(self):
        """Resets the camera to show all elements of the scene"""
        all_elements_rect = self.__scene.itemsBoundingRect()
        viewport = self.viewport()
        viewport_size = (
            viewport.size() if viewport is not None else all_elements_rect.size()
        )
        w_ratio = viewport_size.width() / (all_elements_rect.width() * 1.2)
        h_ratio = viewport_size.height() / (all_elements_rect.height() * 1.2)
        self.cam_pos_zoom = (
            all_elements_rect.center(),
            min(w_ratio, h_ratio),
        )

    def add_stage_sight(
        self, stage: Optional[StageInstrument], camera: Optional[CameraInstrument]
    ):
        """Instantiate a stage sight associated with given stage.

        :param stage: The stage instrument to be associated with the stage sight
        """
        # Add StageSight item
        self.stage_sight = StageSight(stage, camera)
        self.stage_sight.setZValue(1)
        self.__scene.addItem(self.stage_sight)

    @property
    def mode(self) -> Mode:
        """Mode property to indicate in which mode the Viewer is.

        :return: Current selected mode."""
        return self.__mode

    @mode.setter
    def mode(self, new_mode: Mode):
        self.__mode = new_mode
        self.__update_drag_mode()
        self.__update_highlight_color()
        logging.debug(f"Viewer mode selection: {new_mode}")

    def go_next(self):
        """Actions to perform when Laser Studio receive a Go Next command.
        Retrieve the next point position from Scan Geometry
        Inform the StageSight to go to the retrieved position
        """
        if self.scan_geometry:
            next_point = self.scan_geometry.next_point()
            if next_point is not None and self.stage_sight is not None:
                self.stage_sight.move_to(QPointF(*next_point))

    def __update_highlight_color(self, has_shift: Optional[bool] = None):
        """Convenience function to change the current Application Palette to modify
        the highlight color. It permits to the Zone creation tool to have green / red
        colors
        """
        if self.mode != Viewer.Mode.ZONE:
            color = self._default_highlight_color
        else:
            if has_shift is None:
                has_shift = (
                    Qt.KeyboardModifier.ShiftModifier
                    in QGuiApplication.queryKeyboardModifiers()
                )
            color = QColorConstants.Red if has_shift else QColorConstants.Green
        p = QGuiApplication.palette()
        p.setColor(QPalette.ColorRole.Highlight, color)
        QGuiApplication.setPalette(p)

    def __update_drag_mode(self):
        if self.mode == Viewer.Mode.ZONE:
            self.setDragMode(Viewer.DragMode.RubberBandDrag)
        else:
            self.setDragMode(Viewer.DragMode.NoDrag)

    @property
    def cam_pos_zoom(self) -> Tuple[QPointF, float]:
        """'Camera' position and zoom of the Viewer: The first element is
        the position in the stage where the viewer is centered on.
        The second element is the zoom factor, which must be strictly positive.

        :return: A tuple containing the point where the viewer is centered
            on and a float indicating the zoom factor.
        """
        return self.__cam_pos_zoom

    @cam_pos_zoom.setter
    def cam_pos_zoom(self, new_value: Tuple[QPointF, float]):
        assert new_value[1] > 0
        self.__cam_pos_zoom = pos, zoom = new_value
        logging.debug(self.cam_pos_zoom)
        self.resetTransform()
        self.scale(zoom, -zoom)
        self.centerOn(pos)

    # User interactions
    def wheelEvent(self, event: QWheelEvent):
        """
        Handle mouse wheel events to manage zoom.
        """
        if Qt.KeyboardModifier.AltModifier in QGuiApplication.queryKeyboardModifiers():
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

            # The zoom factor to apply
            zr = 2 ** (event.angleDelta().y() / (8 * 120))

            # Get current position and zoom factor of camera
            pos, zoom = self.cam_pos_zoom

            pos = (pos / zr) + (p * (1 - (1 / zr)))
            zoom *= zr

            # Update the position and zoom factors
            self.cam_pos_zoom = pos, zoom
            event.accept()
            return

        super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """
        Called when mouse button is pressed.
        In case of Mode being STAGE, triggers a move of the stage's StageSight.
        """
        is_left = event.button() == Qt.MouseButton.LeftButton

        if self.mode == Viewer.Mode.STAGE and is_left and self.stage_sight is not None:
            # Map the mouse position to the scene position
            scene_pos = self.mapToScene(event.pos())
            self.stage_sight.move_to(scene_pos)
            event.accept()
            return

        # The event is a press of the right button
        if event.button() == Qt.MouseButton.RightButton:
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

    def mouseMoveEvent(self, event: QMouseEvent):
        """
        Called when mouse moves.
        """
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """
        Called when mouse button is released.
        Used to get out the panning, when Right button is released.
        Used to detect the end of the Zone selection.
        """
        is_left = event.button() == Qt.MouseButton.LeftButton
        is_right = event.button() == Qt.MouseButton.RightButton

        if is_right and self.mode != Viewer.Mode.ZONE:
            self.setDragMode(Viewer.DragMode.NoDrag)

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
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """
        Called when key button is released.
        Used when the user hits the SHIFT key in ZONE mode to change
        the color of the rectangle.
        """
        if self.mode == Viewer.Mode.ZONE and Qt.Key.Key_Shift == event.key():
            # In Zone Mode, a release of the Shift key makes the highlight
            # color to be changed to red (remove)
            self.__update_highlight_color()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        """
        Called when key button is released.
        Used when the user hits the SHIFT key in ZONE mode to change
        the color of the rectangle.
        """
        super().keyReleaseEvent(event)
        if self.mode == Viewer.Mode.ZONE and Qt.Key.Key_Shift == event.key():
            # In Zone Mode, a release of the Shift key makes the highlight
            # color to be changed to green (add)
            self.__update_highlight_color()
