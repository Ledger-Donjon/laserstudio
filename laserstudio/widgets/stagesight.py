from PyQt6.QtWidgets import (
    QGraphicsItemGroup,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsLineItem,
)
from PyQt6.QtGui import QPen, QColor, QTransform, QImage, QPixmap
from PyQt6.QtCore import (
    pyqtSignal,
    pyqtBoundSignal,
    QSizeF,
    QLineF,
    QRectF,
    QPointF,
    QObject,
)
from ..instruments.stage import StageInstrument, Vector
from ..instruments.camera import CameraInstrument
from typing import Optional
import logging


class StageSightObject(QObject):
    # Signal emitted when a new position is set
    position_changed = pyqtSignal(QPointF, name="positionChanged")

    def __init__(self, parent=None):
        super().__init__(parent)


class StageSight(QGraphicsItemGroup):
    """
    Item representing the stage position in the scene and the observation area.
    """

    # Signal emitted when a new position is set
    # position_changed = pyqtSignal(Vector, name="positionChanged")

    def __init__(
        self,
        stage: Optional[StageInstrument],
        camera: Optional[CameraInstrument],
        parent=None,
    ):
        super(QGraphicsItemGroup, self).__init__(parent)
        pen = QPen(QColor(0, 100, 255, 150))
        pen.setCosmetic(True)

        self.image_group = QGraphicsItemGroup()
        # Camera image
        self.image = QGraphicsPixmapItem()
        self.image_group.addToGroup(self.image)
        # Area rectangle
        item = self.__rect = QGraphicsRectItem()
        item.setPen(pen)
        self.image_group.addToGroup(item)
        self.addToGroup(self.image_group)

        # Center cross
        item = self.__line1 = QGraphicsLineItem(0, 0, 0, 0)
        item.setPen(pen)
        self.addToGroup(item)
        item = self.__line2 = QGraphicsLineItem(0, 0, 0, 0)
        item.setPen(pen)
        self.addToGroup(item)

        self.__object = StageSightObject()

        self.setPos(QPointF(0.0, 0.0))

        # Associate the StageInstrument
        self.stage = stage
        if stage is not None:
            stage.position_changed.connect(self.update_pos)

        # Associate the CameraInstrument
        self.camera = camera
        if camera is not None:
            camera.new_image.connect(self.set_image)
            self.__update_size(QSizeF(camera.width_um, camera.height_um))
        else:
            self.__update_size(QSizeF(500.0, 500.0))

    def __update_size(self, size: QSizeF):
        """Update the size of the items of the StageSight.

        :param size: the size of the StageSight to be applied."""
        width = size.width()
        height = size.height()

        w2 = width / 2
        h2 = height / 2

        # Update the Area rectangle position
        self.__rect.setRect(-w2, -h2, width, height)

        # Get the enclosing rect into main scene
        scene_rect: QRectF = self.image_group.mapRectToScene(self.__rect.rect())

        # Get the length of the cross' lines according to the size of
        # the enclosing rect.
        rad = min(scene_rect.width(), scene_rect.height()) / 20.0

        # Get the position within the view of the end of the two lines
        self.__line1.setLine(QLineF(rad, 0.0, -rad, 0.0))
        self.__line2.setLine(QLineF(0.0, rad, 0.0, -rad))

        # Set the position and scale of the image
        self.__update_image_size()

    def __update_image_size(self):
        """Apply a transform to change the image' size and position, according
        to current size of Area Rectangle"""
        size = self.__rect.rect().size()

        width = size.width()
        height = size.height()

        w2 = width / 2
        h2 = height / 2

        image = self.image
        image.resetTransform()
        image_size = self.image.pixmap().size()

        transform = QTransform()
        transform.translate(-w2, h2)
        transform.scale(
            width / (image_size.width() or 1.0), -height / (image_size.height() or 1.0)
        )
        image.setTransform(transform)

    def set_image(self, image: QImage):
        """
        Set the PixMap item's image.

        :param image: The image to show
        """
        pixmap = QPixmap.fromImage(image.copy())
        self.image.setPixmap(pixmap)

        # The original image size may have changed
        self.__update_image_size()

    @property
    def size(self) -> QSizeF:
        """Sight size."""
        return self.__rect.rect().size()

    @size.setter
    def width(self, value: QSizeF):
        self.__update_size(value)

    @property
    def show_image(self) -> bool:
        """True if camera image is displayed."""
        return self.image.isVisible()

    @show_image.setter
    def show_image(self, value: bool):
        self.image.setVisible(value)

    def scene_coords_from_stage_coords(self, position: Vector) -> QPointF:
        """Gives the coordinates to apply to the position of the StageSight
        when the stage has the position given in parameters.

        :param position: the coordinates of the stage
        :return: The coordinates to set to the widget to represent the stage
            positioning
        """
        return QPointF(*position.xy.data)

    def stage_coords_from_scene_coords(self, position: QPointF) -> Vector:
        """Gives the coordinates to apply to the stage in order
        that the StageSight aims the given point in Viewer scene.

        :param position: the position to aim in the Viewer scene
        :return: The coordinates to apply to the stage.
        """
        if self.stage is None or self.stage.stage.num_axis == 2:
            return Vector(position.x(), position.y())
        v = self.stage.position
        v[0] = position.x()
        if self.stage.stage.num_axis > 1:
            v[1] = position.y()
        return v

    def move_to(self, position: QPointF):
        """Perform a move operation on associated stage.

        :param position: The position to aim, in the viewer's scene.
        """
        x, y = position.x(), position.y()
        logging.info(f"Move to position {x, y}")

        if self.stage is not None:
            self.stage.move_to(self.stage_coords_from_scene_coords(position), wait=True)
        else:
            self.setPos(position)

    def update_pos(self, position: Vector):
        """Update Widget position according to the stage's position, received in parameter

        :param position: The stage's current position.
        """
        scene_pos = self.scene_coords_from_stage_coords(position)
        self.setPos(scene_pos)
        self.position_changed.emit(scene_pos)

    def setPos(self, value: QPointF):
        self.__object.position_changed.emit(value)
        super(QGraphicsItemGroup, self).setPos(value)

    @property
    def position_changed(self) -> pyqtBoundSignal:
        return self.__object.position_changed
