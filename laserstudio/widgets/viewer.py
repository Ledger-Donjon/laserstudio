from PyQt6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QFileDialog,
    QGraphicsPixmapItem,
)
from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColorConstants,
    QWheelEvent,
    QMouseEvent,
    QKeyEvent,
    QGuiApplication,
    QPalette,
    QPainter,
    QPixmap,
    QTransform,
)
from enum import IntEnum, auto
from typing import Optional, Tuple
from .stagesight import StageSight, StageInstrument, CameraInstrument
import logging
from .scangeometry import ScanGeometry
import numpy as np


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
        PIN = auto()

    # Signal emitted when a new mode is set
    mode_changed = pyqtSignal(int, name="modeChanged")

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

        # Background picture
        self.__picture_item = None
        self.background_picture_path = None

        # Pin points for background picture
        self.pins = []

        # To prevent warning, due to QTBUG-103935 (https://bugreports.qt.io/browse/QTBUG-103935)
        if (vp := self.viewport()) is not None:
            vp.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)

    def follow_stagesight(self, value: bool):
        if self.stage_sight is None or self.stage_sight.stage is None:
            return
        try:
            self.stage_sight.position_changed.disconnect()
        except:
            pass

        if value:
            self.stage_sight.position_changed.connect(
                lambda pos: self.__setattr__("cam_pos_zoom", (pos, self.zoom))
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

    def load_picture(self):
        """Requests loading a backgound picture from the user"""
        filename = QFileDialog.getOpenFileName(self, "Open picture")[0]
        if len(filename):
            # Remove previous picture if defined
            if self.__picture_item is not None:
                self.__scene.removeItem(self.__picture_item)
            item = self.__picture_item = QGraphicsPixmapItem(QPixmap(filename))
            item.setZValue(-10)
            transform = QTransform()
            # We place the image at current camera position
            pos = self.__cam_pos_zoom[0]
            transform.translate(pos.x(), pos.y())
            # Scene Y-axis is up, while for images it shall be down. We flip the
            # image over the Y-axis to show it in the right orientation.
            transform.scale(1, -1)
            transform.translate(
                -item.boundingRect().width() / 2, -item.boundingRect().height() / 2
            )
            item.setTransform(transform)
            self.__scene.addItem(item)

            # Save picture path for when transform is saved.
            self.background_picture_path = filename

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
        logging.getLogger("laserstudio").debug(f"Viewer mode selection: {new_mode}")
        self.mode_changed.emit(int(new_mode))

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
        logging.getLogger("laserstudio").debug(self.cam_pos_zoom)
        self.resetTransform()
        self.scale(zoom, -zoom)
        self.centerOn(pos)

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
        if event.button() == Qt.MouseButton.LeftButton:
            # Map the mouse position to the scene position
            scene_pos = self.mapToScene(event.pos())

            if self.mode == Viewer.Mode.STAGE and self.stage_sight is not None:
                self.stage_sight.move_to(scene_pos)
                event.accept()
                return

            if self.mode == Viewer.Mode.PIN:
                self.pin(scene_pos.x(), scene_pos.y())

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

        if len(self.pins) == 0:
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

        self.pins.append((stage_pos, pix_pos))
        logging.getLogger("laserstudio").debug(f"Pins: {self.pins}")
        if len(self.pins) == 3:
            # Time to recalculate the picture transformation matrix!
            #
            # We have three sets of two points A and B where:
            # - A is a spatial position (from stage)
            # - B is the corresponding position in the picture (in pixels,
            #   picked by the user)
            # To each point we add a third coordinate, set to 1, which will
            # allow us to work with translations.
            #
            # We want to find the 3x3 matrix T such as:
            # T * B1 = A1
            # T * B2 = A2
            # T * B3 = A3
            #
            # Written differently, this gives:
            # T * [B1, B2, B3] = [A1, A2, A3]
            #
            # Thus we have:
            # T = [A1, A2, A3] * Inv([B1, B2, B3])
            points_a = list(p[0] + (1,) for p in self.pins)
            points_b = list(p[1] + (1,) for p in self.pins)
            mat_a = np.matrix(points_a).transpose()
            mat_b = np.matrix(points_b).transpose()
            mat = mat_a * np.linalg.inv(mat_b)
            # Convert to QTransform
            # QTransform uses m31, m32 and m33 for translation, and not
            # m13, m23 and m33. Using the transposed version of mat seems
            # to fix the compatibility.
            qtrans = QTransform(*mat.flatten().tolist()[0]).transposed()
            pic.resetTransform()
            pic.setTransform(qtrans)
            # Clear pin points for future pinning, and leave pin mode.
            self.pins.clear()
            self.mode = self.Mode.NONE
        else:
            # Go to stage mode.
            self.mode = self.Mode.STAGE
