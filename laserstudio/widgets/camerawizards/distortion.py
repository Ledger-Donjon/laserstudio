from __future__ import annotations
import os
from typing import cast, TYPE_CHECKING
from PyQt6.QtCore import QCoreApplication, QPointF, QRectF, Qt
from PyQt6.QtGui import QTransform, QPolygonF, QPixmap
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
    Wizard page where the user gets the camera image and can click on it
    to indicate the position of an object, which makes an association
    of the main stage's position and the object's
    position on the camera.
    """

    def initializePage(self) -> None:
        super(CameraAlignmentPage, self).initializePage()
        self._show_restored()

    def __init__(self, step: int, parent: CameraDistortionWizard):
        super().__init__(parent=parent)

        # The information stored when the user clicks on the image
        self.stage_point: QPointF | None = None  # The stage's position
        # State restored from a previous session, shown on first display.
        self._restored_pixmap: QPixmap | None = None
        self._restored_shown = False

        layout = self.layout()
        assert layout is not None

        # Buttons: clear the clicked point, and move the stage back to the
        # position recorded for this page (restored or just clicked).
        self.reset_position = QPushButton("Reposition")
        self.reset_position.setEnabled(False)
        self.reset_position.clicked.connect(lambda: self.set_position(None))
        self.go_to_button = QPushButton("Go to this position")
        self.go_to_button.setEnabled(False)
        self.go_to_button.clicked.connect(self._go_to_saved_position)
        box = QHBoxLayout()
        box.addWidget(self.reset_position)
        box.addWidget(self.go_to_button)
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
        self.go_to_button.setEnabled(self.stage_point is not None)

    def restore_state(
        self,
        clicked: QPointF | None,
        stage: QPointF | None,
        pixmap: QPixmap | None,
    ) -> None:
        """Restore this page from a previously saved distortion wizard state."""
        self.clicked_point = clicked
        self.stage_point = stage
        self.clicked_image_pixmap = pixmap
        self._restored_pixmap = pixmap
        self._restored_shown = False
        self.reset_position.setEnabled(clicked is not None)
        self.go_to_button.setEnabled(stage is not None)
        self._update_clicked_label()
        self.completeChanged.emit()

    def _show_restored(self) -> None:
        """Display the restored image and clicked-point marker once, if any."""
        if self._restored_shown or self.clicked_point is None:
            return
        self._restored_shown = True
        ss = self.viewer.stage_sight
        if self._restored_pixmap is not None and not self._restored_pixmap.isNull():
            ss.set_pixmap(self._restored_pixmap)
            ss.pause_image_update = True
        scene_pos = ss.mapToScene(self.clicked_point)
        self.viewer.clicked_point_marker.setPos(scene_pos)
        self.viewer.clicked_point_marker.setVisible(True)

    def _go_to_saved_position(self) -> None:
        """Move the stage back to the position recorded for this page."""
        stage = self._stage
        if stage is None or self.stage_point is None:
            return
        position = stage.position
        position[0] = -self.stage_point.x()
        if stage.stage.num_axis > 1:
            position[1] = -self.stage_point.y()
        stage.move_to(position, wait=False)


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
                "Some points may be too much aligned.\n"
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

        # Frame the view on the (now distorted) stage sight. Its scene bounding
        # rect already reflects the applied correction, so this works whatever
        # the transform and the camera resolution are.
        self.viewer.stage_sight.setPos(QPointF(0.0, 0.0))
        rect = self.viewer.stage_sight.sceneBoundingRect()
        if not rect.isEmpty():
            self.viewer.setSceneRect(rect)
            self.viewer.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def apply_transform(self):
        """Apply the transform to the whole application.

        Setting the camera's correction matrix notifies every StageSight (all
        viewers, in both the classic and the new UI) through the camera's
        parameter_changed signal, so the alignment is applied everywhere at
        once. Without a camera we fall back to the main viewer directly.
        """
        if (c := self.wizard().instruments.camera) is not None:
            c.correction_matrix = self.transform
        elif (s := self.wizard().laser_studio.viewer.stage_sight) is not None:
            s.distortion = self.transform
        self.wizard().laser_studio.viewer.reset_camera_to_stage_sight()
        # Persist the per-page state (points, stage positions, images) so the
        # alignment can be reviewed and restored after a restart.
        self.wizard().save_pages()

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

        # Restore the per-page state saved in a previous session (if any).
        self.restore_pages()

    def save_pages(self) -> None:
        """Persist each alignment page (clicked point, stage position, image).

        The clicked point and stage position go into camera.distortion_pages
        (serialized to settings.yaml); the images are saved as PNG files next
        to settings.yaml.
        """
        camera = self.instruments.camera
        if camera is None:
            return
        pages: list[dict] = []
        for i, page in enumerate(self.camera_pages):
            if page.clicked_point is None or page.stage_point is None:
                continue
            entry: dict = {
                "clicked": [page.clicked_point.x(), page.clicked_point.y()],
                "stage": [page.stage_point.x(), page.stage_point.y()],
            }
            pixmap = page.clicked_image_pixmap
            if pixmap is not None and not pixmap.isNull():
                path = f"distortion_page_{i}.png"
                if pixmap.save(path, "PNG"):
                    entry["image"] = path
            pages.append(entry)
        camera.distortion_pages = pages

    def restore_pages(self) -> None:
        """Restore each alignment page from camera.distortion_pages."""
        camera = self.instruments.camera
        if camera is None:
            return
        for i, entry in enumerate(camera.distortion_pages):
            if i >= len(self.camera_pages) or not isinstance(entry, dict):
                break
            clicked = entry.get("clicked")
            stage = entry.get("stage")
            pixmap: QPixmap | None = None
            image = entry.get("image")
            if isinstance(image, str) and os.path.exists(image):
                candidate = QPixmap(image)
                if not candidate.isNull():
                    pixmap = candidate
            self.camera_pages[i].restore_state(
                QPointF(clicked[0], clicked[1]) if clicked else None,
                QPointF(stage[0], stage[1]) if stage else None,
                pixmap,
            )

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

        # First polygon's points, in the image space. The clicked points are in
        # centered pixel coordinates; they are normalized to [-1, 1] relative to
        # the camera resolution so that the resulting transform (and hence the
        # saved correction matrix) is independent of the camera resolution.
        camera = self.instruments.camera
        if camera is None:
            return None
        half_w = camera.width / 2.0
        half_h = camera.height / 2.0
        if not half_w or not half_h:
            return None
        one = [
            QPointF(page.clicked_point.x() / half_w, page.clicked_point.y() / half_h)
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
