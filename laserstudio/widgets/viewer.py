from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene
from PyQt6.QtCore import Qt, QPointF, QRectF, QPoint
from PyQt6.QtGui import (
    QBrush,
    QColorConstants,
    QWheelEvent,
    QMouseEvent,
    QGuiApplication,
)
from enum import IntEnum, auto
from typing import Optional, Tuple
from .stagesight import StageSight, StageInstrument, Vector
import logging


class Viewer(QGraphicsView):
    """
    Widget to display circuit photos, navigate and control position, display the
    results...
    """

    class Mode(IntEnum):
        """Viewer modes."""

        NONE = auto()
        STAGE = auto()

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

        # Hide scrollbars
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


        # Current camera position and zoom factor
        self.__cam_pos_zoom = QPointF(), 1.0
        self.scale(1, -1)

        # By default, there is no StageSight
        self.stage_sight = None

        self.setInteractive(True)

    def reset_camera(self):
        """Resets the camera to show all elements of the scene"""
        self.cam_pos_zoom = (
            self.__scene.itemsBoundingRect().center(),
            self.cam_pos_zoom[1],
        )

    def add_stage_sight(self, stage: StageInstrument):
        """Instantiate a stage sight associated with given stage.

        :param stage: The stage instrument to be associated with the stage sight
        """
        # Add StageSight item
        item = self.stage_sight = StageSight(stage)
        self.__scene.addItem(item)

    @property
    def mode(self) -> Mode:
        """Mode property to indicate in which mode the Viewer is.

        :return: Current selected mode."""
        return self.__mode

    @mode.setter
    def mode(self, new_mode: Mode):
        self.__mode = new_mode
        logging.debug(f"Viewer mode selection: {new_mode}")
        if new_mode == Viewer.Mode.NONE:
            self.setDragMode(Viewer.DragMode.NoDrag)
        elif new_mode == Viewer.Mode.STAGE:
            self.setDragMode(Viewer.DragMode.NoDrag)

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
    def mousePressEvent(self, event: QMouseEvent):
        """
        Called when mouse button is pressed.
        """
        is_left = event.button() == Qt.MouseButton.LeftButton

        if self.mode == Viewer.Mode.STAGE and is_left and self.stage_sight is not None:
            # Map the mouse position to the scene position
            scene_pos = self.mapToScene(event.pos())
            self.stage_sight.move_to(Vector(scene_pos.x(), scene_pos.y()))
            event.accept()
            return

        # The event is a press of the right button
        if event.button() == Qt.MouseButton.RightButton:
            # Scroll gesture mode
            self.setDragMode(Viewer.DragMode.ScrollHandDrag)
            # Transform as left press button event
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
        In the case where the right button is pressed, moves the position.
        """
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """
        Called when mouse button is released.
        """
        if event.button() == Qt.MouseButton.RightButton:
            self.setDragMode(Viewer.DragMode.NoDrag)
        super().mouseReleaseEvent(event)
