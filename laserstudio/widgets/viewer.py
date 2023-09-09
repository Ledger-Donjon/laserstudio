from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QBrush, QColorConstants, QWheelEvent, QMouseEvent
from enum import IntEnum, auto
from typing import Optional, Tuple
from .stagesight import StageSight


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

        # Disable scrollbars
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Add StageSight item
        item = self.stage_sight = StageSight()
        self.__scene.addItem(item)

        # Current position and zoom factors where the Viewer is focusing
        self.__cam_pos_zoom = QPointF(0.0, 0.0), 1.0

    @property
    def mode(self) -> Mode:
        """Mode property to indicate in which mode the Viewer is.

        :return: Current selected mode."""
        return self.__mode

    @mode.setter
    def mode(self, new_mode: Mode):
        self.__mode = new_mode

    def wheelEvent(self, event: QWheelEvent):
        """
        Handle mouse wheel events to manage zoom.
        """
        # We want to zoom relative to the current cursor position, not relative
        # to the center of the widget. This involves some math...
        # p is the pointed position in the scene, and we want to keep p at the
        # same screen position after changing the zoom. If c1 and c2 are the
        # camera before and after, z1 and z2 the zoom levels, then we want:
        # z1 * (p - c1) = z2 * (p - c2)
        # which gives:
        # c2 = c1 * (z1/z2) + p * (1 - z1/z2)
        # we can use zr = z2/z1, the zoom factor to apply between two events.

        p = self.mapToScene(event.position().toPoint())
        zr = 2 ** ((event.angleDelta().y() * 0.25) / 120)

        pos, zoom = self.__cam_pos_zoom
        pos = (pos / zr) + ((1 - (1 / zr)) * p)
        zoom = zoom * zr
        self.cam_pos_zoom = pos, zoom

    def __reset_transform(self):
        self.resetTransform()
        pos, zoom = self.cam_pos_zoom
        self.centerOn(pos)
        self.scale(zoom, zoom)

    @property
    def cam_pos_zoom(self) -> Tuple[QPointF, float]:
        """Camera position of the viewer: The given point is
        the position that the viewer is focussing on, the second element
        of the tuple is the zoom factor, which must be strictly positive.

        :return: A tuple containing the point where the viewer is focussing
            on and a float indicating the zoom factor.
        """
        return self.__cam_pos_zoom

    @cam_pos_zoom.setter
    def cam_pos_zoom(self, new_value: Tuple[QPointF, float]):
        assert new_value[1] > 0
        self.__cam_pos_zoom = new_value
        self.__reset_transform()

    # User interactions
    def mousePressEvent(self, event: QMouseEvent):
        """
        Called when mouse button is pressed.
        """
        self.__mouse_prev_pos = event.pos()

    def mouseMoveEvent(self, event: QMouseEvent):
        """
        Called when mouse moves.
        In the case where the right button is pressed, moves the position.
        """
        if self.__mouse_prev_pos is None:
            self.__mouse_prev_pos = event.pos()
        delta = event.pos() - self.__mouse_prev_pos

        is_right = Qt.MouseButton.RightButton in event.buttons()

        # Panning management
        if is_right:
            cam_pos, cam_zoom = self.cam_pos_zoom
            cam_pos -= delta.toPointF() / cam_zoom
            self.cam_pos_zoom = cam_pos, cam_zoom

        self.__mouse_prev_pos = event.pos()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """
        Called when mouse button is released.
        """
        if not event.buttons():
            self.__mouse_prev_pos = None
