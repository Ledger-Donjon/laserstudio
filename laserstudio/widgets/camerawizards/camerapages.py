from __future__ import annotations

from enum import Enum, auto
from typing import cast, TYPE_CHECKING, Any
from PyQt6.QtWidgets import (
    QWizardPage,
    QWizard,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import (
    pyqtSignal,
    Qt,
    QPointF,
)
from PyQt6.QtGui import (
    QMouseEvent,
    QWheelEvent,
    QPixmap,
)
from ..marker import Marker
from ...instruments.instruments import CameraInstrument
from ..stagesight import StageSight, StageSightViewer

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class PagesID(int, Enum):
    INTRO = auto()

    ALIGN = auto()
    ALIGN_RESULT = ALIGN + 4

    PROBE_POSITION = ALIGN

    FINAL = -1


class CameraPicker(StageSightViewer):
    """
    A StageSightViewer in which a user can zoom and pan.
    This viewer presents the image of the camera.
    The size of the image is in pixels: we do not consider
    the objective and the pixel to micrometer ratio (if any).
    It permits to pick a relative point on the image in pixels.
    """

    # Signal emitted when the graphic view is clicked
    clicked = pyqtSignal(tuple)

    def mousePressEvent(self, event: QMouseEvent | None):
        """
        Click in the stagesight.
        """
        assert event is not None
        if event.button() == Qt.MouseButton.LeftButton:
            self.panning = True
            pos = event.pos()
            self.clicked.emit((pos.x(), pos.y()))
        if event.button() == Qt.MouseButton.RightButton:
            # Scroll gesture mode
            self.setDragMode(CameraPicker.DragMode.ScrollHandDrag)
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

    def mouseMoveEvent(self, event: QMouseEvent | None):
        """
        Mouse is moving, do something if the panning is ongoing.
        """
        assert event is not None
        if self.panning:
            pos = event.pos()
            self.clicked.emit((pos.x(), pos.y()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None):
        """
        Click release.
        """
        assert event is not None
        if event.button() == Qt.MouseButton.LeftButton:
            self.panning = False
            pos = event.pos()
            self.clicked.emit((pos.x(), pos.y()))
        if event.button() == Qt.MouseButton.RightButton:
            self.setDragMode(CameraPicker.DragMode.NoDrag)

    def __compute_pos(self):
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

        return QPointF(scene_x, scene_y)

    def wheelEvent(self, event: QWheelEvent | None):
        """
        Handle mouse wheel events to manage zoom.
        """
        if event is None:
            return
        # Get current position of camera
        pos = self.__compute_pos()
        # The zoom factor to apply
        zr = 2 ** (event.angleDelta().y() / (8 * 120))
        # The pointed position
        p = self.mapToScene(event.position().toPoint())
        pos = (pos / zr) + (p * (1 - (1 / zr)))

        self.zoom *= zr
        self.resetTransform()
        self.scale(self.zoom, -self.zoom)
        self.centerOn(pos)
        event.accept()

    def __init__(self, camera: CameraInstrument, *args: Any):
        s = StageSight(stage=None, camera=camera)
        s.update_size(in_pixels=True)
        super().__init__(stage_sight=s, *args)
        self.zoom = 1.0
        self.panning = False
        self.clicked_point_marker = Marker()
        # Set scale to 5 percent of the image size
        self.clicked_point_marker.size = 0.05 * s.size.width()
        s = self.scene()
        assert s is not None
        s.addItem(self.clicked_point_marker)
        self.clicked_point_marker.setVisible(False)
        self.reset_camera()


class CameraWizardPage(QWizardPage):
    def wizard(self) -> CameraWizard:
        return cast(CameraWizard, super().wizard())


class CameraPresentationPage(CameraWizardPage):
    """
    Wizard page where the user gets the camera image.
    """

    def __init__(self, parent: CameraWizard):
        super().__init__(parent)
        camera = parent.instruments.camera
        assert camera is not None
        layout = QVBoxLayout()

        # The viewer for showing camera
        self.viewer = viewer = CameraPicker(camera)
        viewer.setMinimumHeight(400)
        layout.addWidget(viewer)
        self.setLayout(layout)


class CameraPositionPage(CameraPresentationPage):
    """
    Wizard page where the user gets the camera image and can click
    on it to indicate the position of an object
    """

    def set_position(self, xy: tuple[int, int] | None):
        # (De)activate the update of the image in StageSight
        self.viewer.stage_sight.pause_image_update = xy is not None
        if xy is None:
            self.clicked_point = None
            self.clicked_image_pixmap = None
        else:
            # Place the marker to clicked point
            in_scene = self.viewer.mapToScene(*xy)
            self.viewer.clicked_point_marker.setPos(in_scene)
            # We want the position of point within the StageSight view.
            self.clicked_point = self.viewer.stage_sight.mapFromScene(in_scene)
            # Save the image
            self.clicked_image_pixmap = self.viewer.stage_sight.image.pixmap()

        self.viewer.clicked_point_marker.setVisible(xy is not None)
        self.completeChanged.emit()

    def __init__(self, parent: CameraWizard):
        super().__init__(parent=parent)
        # The coordinates of the point within the camera
        self.clicked_point: QPointF | None = None
        self.viewer.clicked.connect(self.set_position)
        # The pixmap of image when the user clicked
        self.clicked_image_pixmap: QPixmap | None = None


class CameraWizard(QWizard):
    def __init__(self, laser_studio: LaserStudio, parent: QWidget | None = None):
        super().__init__(parent)

        self.instruments = laser_studio.instruments
        self.laser_studio = laser_studio
