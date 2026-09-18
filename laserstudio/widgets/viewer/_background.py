from __future__ import annotations
from PyQt6.QtWidgets import QGraphicsPixmapItem, QFileDialog
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QTransform, QPixmap
from laserstudio.utils.background_align import BackgroundPin, compute_affine_transform
from ._base import _ViewerBase


class _BackgroundMixin(_ViewerBase):
    """Management of the background reference picture: loading, placement,
    opacity, pin-based alignment and camera framing helpers."""

    def reset_camera(self, item: QGraphicsPixmapItem | None = None):
        """Resets the camera to show all elements of the scene"""
        if item is not None:
            all_elements_rect = item.sceneTransform().mapRect(item.boundingRect())
            if all_elements_rect.width() <= 0 or all_elements_rect.height() <= 0:
                self.reset_camera_to_stage_sight()
                return
        else:
            all_elements_rect = self._scene.itemsBoundingRect()
        self._apply_camera_fit(all_elements_rect)

    def _visible_items_rect(self) -> QRectF:
        """Bounding rect of the items actually drawn.

        ``QGraphicsScene.itemsBoundingRect`` also covers hidden items — the
        guardrail circle alone spans tens of millimetres — so framing it would
        leave the user staring at empty scene.
        """
        rect = QRectF()
        for item in self._scene.items():
            if item.isVisible():
                rect = rect.united(item.sceneBoundingRect())
        return rect

    def reset_camera_to_visible_items(self):
        """Resets the camera to frame every element currently drawn."""
        rect = self._visible_items_rect()
        if rect.isNull():
            self.reset_camera()
            return
        self._apply_camera_fit(rect)

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

    def _place_picture_item(self, at_stage_sight: bool = False):
        item = self._picture_item
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
        self._scene.addItem(item)
        item.setOpacity(self._background_opacity)
        self._background_base_transform = QTransform(item.transform())
        self._background_committed_pins.clear()
        self.background_changed.emit()

    def _set_picture_item(self, item: QGraphicsPixmapItem):
        item = self._picture_item = QGraphicsPixmapItem(item.pixmap())

    def snap_picture_from_camera(self):
        """Takes the current picture from the current
        and set it as background picture"""
        if self.stage_sight is None:
            return
        self.clear_picture()
        self._set_picture_item(self.stage_sight.image)
        self._place_picture_item(at_stage_sight=True)

    def clear_picture(self):
        """Clears the background picture"""
        if self._picture_item is not None:
            self._scene.removeItem(self._picture_item)
            self._picture_item = None
            self.background_picture_path = None
            self._background_base_transform = None
            self._background_committed_pins.clear()
            self.pins.clear()
            for m in self.pin_markers:
                m.hide()
            self.background_changed.emit()

    @property
    def has_background_picture(self) -> bool:
        return self._picture_item is not None

    @property
    def background_opacity(self) -> int:
        """Opacity percentage (0–100) for the reference image."""
        return int(round(self._background_opacity * 100))

    def set_background_opacity(self, percent: int) -> None:
        self._background_opacity = max(0.0, min(100, percent)) / 100.0
        if self._picture_item is not None:
            self._picture_item.setOpacity(self._background_opacity)
        self.background_changed.emit()

    @property
    def background_is_aligned(self) -> bool:
        return len(self._background_committed_pins) == 3

    @property
    def background_committed_pins(self) -> list[BackgroundPin]:
        return list(self._background_committed_pins)

    def background_pixmap(self) -> QPixmap | None:
        if self._picture_item is None:
            return None
        return self._picture_item.pixmap()

    def background_picture_transform(self) -> QTransform | None:
        if self._picture_item is None:
            return None
        return QTransform(self._picture_item.transform())

    def restore_background_transform(
        self, transform: QTransform | None
    ) -> None:
        """Restore the background picture transform (e.g. after canceling a preview)."""
        pic = self._picture_item
        if pic is None:
            return
        if transform is None:
            self._restore_background_base_transform()
            return
        pic.resetTransform()
        pic.setTransform(QTransform(transform))

    def _restore_background_base_transform(self) -> None:
        pic = self._picture_item
        if pic is None or self._background_base_transform is None:
            return
        pic.resetTransform()
        pic.setTransform(QTransform(self._background_base_transform))

    def preview_background_alignment(
        self, pins: list[BackgroundPin]
    ) -> bool:
        """Apply a temporary affine transform from *pins* (preview, not committed)."""
        pic = self._picture_item
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

    def capture_background_pin(
        self, image_px: tuple[float, float]
    ) -> BackgroundPin:
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
            self._set_picture_item(item)
            self._place_picture_item()
            # Save picture path for when transform is saved.
            self.background_picture_path = filename
