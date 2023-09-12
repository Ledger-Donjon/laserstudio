from PyQt6.QtWidgets import (
    QGraphicsItemGroup,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsLineItem,
)
from PyQt6.QtGui import QPen, QColor, QTransform, QImage, QPixmap
from PyQt6.QtCore import QSizeF, QLineF, QRectF, QPointF
from ..instruments.stage import StageInstrument, Vector
from typing import Optional
import logging


class StageSight(QGraphicsItemGroup):
    """
    Item representing the stage position in the scene and the observation area.
    """

    def __init__(self, stage: Optional[StageInstrument], parent=None):
        super().__init__(parent)
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

        self.__update_size(QSizeF(1000.0, 1000.0))
        self.setPos(0.0, 0.0)

        # Associate the StageInstrument
        self.stage = stage

        if stage is not None:
            stage.position_changed.connect(lambda pos: self.setPos(*(pos.xy.data)))

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
        rect = image.boundingRect()

        transform = QTransform()
        transform.translate(-w2, h2)
        transform.scale(rect.width() / width, rect.height() / height)
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

    def move_to(self, position: Vector):
        """Perform a move operation on associated stage.

        :param position: The position to aim.
        """
        logging.info(f"Move to position {position.data}")

        if self.stage is not None:
            self.stage.move_to(position, wait=True)
