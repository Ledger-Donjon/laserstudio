from __future__ import annotations
from typing import cast, TYPE_CHECKING
from PyQt6.QtCore import QCoreApplication, QPointF, QRectF, Qt
from PyQt6.QtGui import QTransform, QPolygonF
from PyQt6.QtWidgets import QWidget, QPushButton, QHBoxLayout
from .camerapages import (
    CameraWizardPage,
    CameraPresentationPage,
    CameraPositionPage,
    CameraWizard,
)
from .camerapages import PagesID

if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class DistortionIntroductionPage(CameraWizardPage):
    def __init__(self, parent: CameraDistortionWizard):
        super().__init__(parent)
        self.setTitle("Camera distortion wizard")
        self.setSubTitle(
            "This tool permits to "
            "correct the distortion of the camera image "
            "when the camera vertically placed."
        )

    def nextId(self) -> int:
        return PagesID.ALIGN


class CameraAlignmentPage(CameraPositionPage):
    """
    Wizard page where the user get the camera image and can click on it to indicate the position of
    an object which makes an association of the main stage's position and the object's
    position on the camera.
    """

    def initializePage(self) -> None:
        super(CameraAlignmentPage, self).initializePage()

    def __init__(self, step: int, parent: CameraDistortionWizard):
        super().__init__(parent=parent)

        # The information stored when the user clicks on the image
        self.stage_point: QPointF | None = None  # The stage's position

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

    def set_position(self, xy: tuple[int, int] | None):
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

    def wizard(self) -> CameraDistortionWizard:
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
        self.wizard().laser_studio.viewer.reset_camera_to_stage_sight()

    def __init__(self, parent: CameraDistortionWizard):
        super().__init__(parent=parent)
        layout = self.layout()
        assert layout is not None

        self.transform: QTransform | None = None

        self.apply_button = w = QPushButton(
            f"Apply to {QCoreApplication.applicationName()}"
        )
        w.clicked.connect(self.apply_transform)
        layout.addWidget(w)
        self.setTitle("Camera Alignment Result")


class CameraDistortionWizard(CameraWizard):
    def __init__(self, laser_studio: LaserStudio, parent: QWidget | None = None):
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
    def transform(self) -> QTransform | None:
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
