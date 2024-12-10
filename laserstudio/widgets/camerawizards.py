from PyQt6.QtWidgets import (
    QWizardPage,
    QWizard,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
    QWidget,
)
from PyQt6.QtCore import (
    pyqtSignal,
    Qt,
    QPointF,
    QRectF,
    QCoreApplication,
)
from PyQt6.QtGui import (
    QMouseEvent,
    QWheelEvent,
    QPixmap,
    QTransform,
    QPolygonF,
    QColorConstants,
)
from enum import Enum, auto

from .marker import Marker
from ..instruments.instruments import CameraInstrument
from ..instruments.instruments import ProbeInstrument, LaserInstrument
from .stagesight import StageSight, StageSightViewer
from typing import cast, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..laserstudio import LaserStudio


class PagesID(int, Enum):
    INTRO = auto()

    ALIGN = auto()
    ALIGN_RESULT = ALIGN + 4

    PROBE_POSITION = ALIGN

    FINAL = -1


class CameraPicker(StageSightViewer):
    """
    A StageSightViewer in which a user can zoom and pan.
    """

    # Signal emitted when the graphic view is clicked
    clicked = pyqtSignal(tuple)

    def mousePressEvent(self, event: Optional[QMouseEvent]):
        """
        Click in the stagesight.
        """
        assert event is not None
        if event.button() == Qt.MouseButton.LeftButton:
            self.panning = True
            pos = event.pos()
            self.clicked.emit((pos.x(), pos.y()))

    def mouseMoveEvent(self, event: Optional[QMouseEvent]):
        """
        Mouse is moving, do something if the panning is ongoing.
        """
        assert event is not None
        if self.panning:
            pos = event.pos()
            self.clicked.emit((pos.x(), pos.y()))

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]):
        """
        Click release.
        """
        assert event is not None
        if event.button() == Qt.MouseButton.LeftButton:
            self.panning = False
            pos = event.pos()
            self.clicked.emit((pos.x(), pos.y()))

    def wheelEvent(self, event: Optional[QWheelEvent]):
        """
        Handle mouse wheel events to manage zoom.
        """
        assert event is not None
        zr = 2 ** ((event.angleDelta().y() * 0.25) / 120)
        self.zoom *= zr
        self.resetTransform()
        self.scale(self.zoom, -self.zoom)

    def __init__(self, camera: CameraInstrument, *args):
        s = StageSight(stage=None, camera=camera)
        super().__init__(stage_sight=s, *args)
        self.zoom = 0.1
        self.panning = False
        self.clicked_point_marker = Marker()
        s = self.scene()
        assert s is not None
        s.addItem(self.clicked_point_marker)
        self.clicked_point_marker.setVisible(False)
        self.reset_camera()


class CameraWizardPage(QWizardPage):
    def wizard(self) -> "CameraWizard":
        return cast(CameraWizard, super().wizard())


class ProbePositionIntroductionPage(CameraWizardPage):
    def __init__(self, parent: "ProbesPositionWizard"):
        super().__init__(parent)
        self.setTitle("Probe position wizard")
        self.setSubTitle(
            "This tool permits to indicate where in the image "
            "the probe or the laser spot appears. This permits to "
            "laser studio to accomodate the move of the stage in order "
            "that the probe or the spot is placed at the desired point instead "
            "of the center of the camera."
        )

    def nextId(self) -> int:
        return PagesID.PROBE_POSITION


class DistortionIntroductionPage(CameraWizardPage):
    def __init__(self, parent: "CameraDistortionWizard"):
        super().__init__(parent)
        self.setTitle("Camera distortion wizard")
        self.setSubTitle(
            "This tool permits to "
            "correct the distortion of the camera image "
            "when the camera vertically placed."
        )

    def nextId(self) -> int:
        return PagesID.ALIGN


class CameraPresentationPage(CameraWizardPage):
    """
    Wizard page where the user gets the camera image.
    """

    def __init__(self, parent: "CameraWizard"):
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
    Wizard page where the user get the camera image and can click
    on it to indicate the position of an object
    """

    def set_position(self, xy: Optional[tuple[int, int]]):
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

    def __init__(self, parent: "CameraWizard"):
        super().__init__(parent=parent)
        # The coordinates of the point within the camera
        self.clicked_point: Optional[QPointF] = None
        self.viewer.clicked.connect(self.set_position)
        # The pixmap of image when the user clicked
        self.clicked_image_pixmap: Optional[QPixmap] = None


class CameraAlignmentPage(CameraPositionPage):
    """
    Wizard page where the user get the camera image and can click on it to indicate the position of
    an object which makes an association of the main stage's position and the object's
    position on the camera.
    """

    def initializePage(self) -> None:
        super(CameraAlignmentPage, self).initializePage()

    def __init__(self, step: int, parent: "CameraDistortionWizard"):
        super().__init__(parent=parent)

        # The information stored when the user clicks on the image
        self.stage_point: Optional[QPointF] = None  # The stage's position

        layout = self.layout()
        assert layout is not None
        # # A Keyboard box to control the stage
        # self.keyboard_box = KeyboardBox(parent.instruments.stage)
        # layout.addWidget(self.keyboard_box)

        # A Button permitting to reposition the stage
        self.reset_position = QPushButton("Reposition")
        self.reset_position.setEnabled(False)
        self.reset_position.clicked.connect(lambda: self.set_position(None))
        box = QHBoxLayout()
        box.addWidget(self.reset_position)
        w = QWidget()
        w.setLayout(box)
        layout.addWidget(w)

        self.setTitle(f"Camera Alignment (step {step} of 4)")
        self.setSubTitle(
            "Move your stage to place a distinguishable object at one corner of the camera "
            "and click on the image to position the object."
        )

    def set_position(self, xy: Optional[tuple[int, int]]):
        super().set_position(xy)

        # Enable/disable some UI elements
        # self.keyboard_box.setEnabled(xy is None)
        self.reset_position.setEnabled(xy is not None)

        # Reset the position of stage
        self.stage_point = None

        if (
            xy is not None
            and self.stage_point is None
            and ((s := self.wizard().instruments.stage) is not None)
        ):
            # Retrieve position of the stage
            self.stage_point = -QPointF(*s.position.xy)


class DistortedImagePresentationPage(CameraPresentationPage):
    """
    Wizard page where the user can see the result of the distortion.
    """

    def wizard(self) -> "CameraDistortionWizard":
        return cast(CameraDistortionWizard, super().wizard())

    def initializePage(self):
        self.transform = self.wizard().transform
        self.viewer.stage_sight.resetTransform()
        if self.transform is None:
            self.setSubTitle(
                "The computation of the distortion correction failed.\n"
                "Some points may be to much aligned."
                "Please retry.",
            )
            self.apply_button.setEnabled(False)
            return
        else:
            self.setSubTitle(
                "The computation of the distortion correction succeeded.\n"
                "If you are satisfied with this result, click Apply",
            )
            self.viewer.stage_sight.distortion = self.transform
            self.apply_button.setEnabled(True)

        w, h = (
            self.viewer.stage_sight.size.width(),
            self.viewer.stage_sight.size.height(),
        )

        # The transform may induce a translation
        # which can be measured by mapping the origin
        delta = self.transform.map(QPointF(0.0, 0.0))
        rect = self.transform.mapRect(QRectF(-w / 2, -h / 2, w, h))
        self.viewer.stage_sight.setPos(delta)
        self.viewer.setSceneRect(rect)
        self.viewer.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def apply_transform(self):
        """Apply the transform to main application"""
        if (s := self.wizard().laser_studio.viewer.stage_sight) is not None:
            s.distortion = self.transform
        if (c := self.wizard().instruments.camera) is not None:
            c.correction_matrix = self.transform
        # self.wizard().laser_studio.update_stage_sight()

    def __init__(self, parent: "CameraDistortionWizard"):
        super().__init__(parent=parent)
        layout = self.layout()
        assert layout is not None

        self.transform: Optional[QTransform] = None

        self.apply_button = w = QPushButton(
            f"Apply to {QCoreApplication.applicationName()}"
        )
        w.clicked.connect(self.apply_transform)
        layout.addWidget(w)
        self.setTitle("Camera Alignment Result")


class ProbePositionPage(CameraPositionPage):
    """
    Wizard page where the user get the camera image and can click
    on it to indicate the position of a probe/spot relatively to the
    camera image
    """

    def __init__(
        self, probe_index: int, probe: ProbeInstrument, parent: "ProbesPositionWizard"
    ):
        super().__init__(parent=parent)
        if isinstance(probe, LaserInstrument):
            what = "Laser Spot"
            self.viewer.clicked_point_marker.color = QColorConstants.Red
        else:
            what = "Probe"
            self.viewer.clicked_point_marker.color = QColorConstants.Blue
        self.setTitle(f"{what} {probe_index+1} positioning")
        self.setSubTitle(
            f"Indicate in the image the position of the {what}."
            f" This operation will permit {QCoreApplication.applicationName()} to move accordingly to"
            " indicated point instead of the center of the image"
        )
        self.probe = probe

    def set_position(self, xy: Optional[tuple[int, int]]):
        super().set_position(xy)
        self.viewer.stage_sight.pause_image_update = False
        if self.clicked_point is not None:
            self.probe.offset_pos = self.clicked_point.x(), self.clicked_point.y()


class CameraWizard(QWizard):
    def __init__(self, laser_studio: "LaserStudio", parent=None):
        super().__init__(parent)

        self.instruments = laser_studio.instruments
        self.laser_studio = laser_studio


class ProbesPositionWizard(CameraWizard):
    def __init__(self, laser_studio: "LaserStudio", parent=None):
        super().__init__(laser_studio=laser_studio, parent=parent)
        # Create the ProbePositionIntroductionPage page
        self.setPage(PagesID.INTRO, ProbePositionIntroductionPage(parent=self))

        # Create pages for probe position
        page = 0
        for probe in enumerate(laser_studio.instruments.probes):
            self.setPage(
                PagesID.PROBE_POSITION + page,
                ProbePositionPage(*probe, parent=self),
            )
            page += 1
        for laser in enumerate(laser_studio.instruments.lasers):
            self.setPage(
                PagesID.PROBE_POSITION + page,
                ProbePositionPage(*laser, parent=self),
            )
            page += 1


class CameraDistortionWizard(CameraWizard):
    def __init__(self, laser_studio: "LaserStudio", parent=None):
        super().__init__(laser_studio=laser_studio, parent=parent)
        # Create the DistortionIntroductionPage page
        self.setPage(PagesID.INTRO, DistortionIntroductionPage(parent=self))

        # Creates four alignment pages
        self.camera_pages: list[CameraAlignmentPage] = []
        for step in range(4):
            p = CameraAlignmentPage(step=step + 1, parent=self)
            self.camera_pages.append(p)
            self.setPage(PagesID.ALIGN + step, p)
        self.setPage(PagesID.ALIGN_RESULT, DistortedImagePresentationPage(parent=self))

    @property
    def transform(self) -> Optional[QTransform]:
        """
        Computes the transformation matrix according to the four pairs of points (stage
            points/clicked points) from the four configuration pages.

        :return: The transformation matrix to be applied to the camera image to make
            it appear not-distorted.
        """

        # To construct a correction matrix, we have to give two quadrangles, for which all
        # four angle's coordinates are corresponding to a mapping from one 'space' to another
        # 'space'.

        # First polygon's points (view's space, in pixel)
        one = [
            page.clicked_point
            for page in self.camera_pages
            if page.clicked_point is not None
        ]
        # Second polygon's points (stage's space, in micrometer)
        two = [
            page.stage_point
            for page in self.camera_pages
            if page.stage_point is not None
        ]

        # The two polygons must have 4 points each
        if len(one) != 4 or len(two) != 4:
            return None

        transform = QTransform()
        ok = QTransform.quadToQuad(QPolygonF(one), QPolygonF(two), transform)
        return transform if ok else None
