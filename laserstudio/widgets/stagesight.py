from PyQt6.QtWidgets import (
    QGraphicsItemGroup,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsLineItem,
    QGraphicsView,
    QGraphicsScene,
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
from ..instruments.probe import ProbeInstrument
from ..instruments.laser import LaserInstrument
from typing import Optional, Union
import logging
from .marker import ProbeMarker


class StageSightViewer(QGraphicsView):
    """Simple version of Viewer, containing a StageSight"""

    def __init__(self, stage_sight: "StageSight", parent=None):
        super().__init__(parent)
        self.stage_sight = stage_sight
        self.__scene = s = QGraphicsScene(self)
        self.scale(1, -1)
        self.setScene(s)
        s.addItem(stage_sight)

    def reset_camera(self):
        """Show all elements of the scene"""
        all_elements_rect = self.__scene.itemsBoundingRect()
        viewport = self.viewport()
        viewport_size = (
            viewport.size() if viewport is not None else all_elements_rect.size()
        )
        w_ratio = viewport_size.width() / (all_elements_rect.width() * 1.2)
        h_ratio = viewport_size.height() / (all_elements_rect.height() * 1.2)
        new_value = (
            all_elements_rect.center(),
            min(w_ratio, h_ratio),
        )
        self.resetTransform()
        self.scale(new_value[1], -new_value[1])
        self.centerOn(new_value[0])


class StageSightObject(QObject):
    """Proxy object for signal emission, StageSight, as
    inheriting QGraphicsItemGroup, cannot inherit from QObject."""

    # Signal emitted when a new position is set
    position_changed = pyqtSignal(QPointF)

    def __init__(self, parent=None):
        super().__init__(parent)


class StageSight(QGraphicsItemGroup):
    """
    Item representing the stage position in the scene and the observation area.
    """

    # Signal emitted when a new position is set.
    # This has been placed in a proxy object (StageSightObject)
    # Because QGraphicsItemGroup does not inherit from QObject.
    # A convenient property is defined to access to the proxy's signal
    # position_changed = pyqtSignal(Vector, name="positionChanged")

    def __init__(
        self,
        stage: Optional[StageInstrument],
        camera: Optional[CameraInstrument],
        probes: list[ProbeInstrument] = [],
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
        self.update_size()

        # Create Markers for probes
        self._probe_markers: list[ProbeMarker] = []
        for probe in probes:
            marker = ProbeMarker(probe, self)
            self.addToGroup(marker)
            self._probe_markers.append(marker)

    def update_size(self):
        """Update the size of the StageSight according to the camera."""
        if self.camera is not None:
            self._pause_update = False
            self.camera.new_image.connect(self.set_image)
            self.__update_size(QSizeF(self.camera.width_um, self.camera.height_um))
        else:
            self.__update_size(QSizeF(500.0, 500.0))

    @property
    def pause_image_update(self) -> bool:
        """Permits to pause the image update when receiving the 'new_image' signal from the camera."""
        return self._pause_update

    @pause_image_update.setter
    def pause_image_update(self, value: bool):
        if self.camera is None:
            return
        if self._pause_update != value:
            if value:
                self.camera.new_image.disconnect(self.set_image)
            else:
                self.camera.new_image.connect(self.set_image)
        self._pause_update = value

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

    def set_pixmap(self, pixmap: QPixmap):
        """
        Set the PixMap item's image.

        :param image: The image to show
        """
        self.image.setPixmap(pixmap)

        # The original image size may have changed
        self.__update_image_size()

    def set_image(self, image: QImage):
        """
        Set the item's image.

        :param image: The image to show
        """
        pixmap = QPixmap.fromImage(image.copy())
        self.set_pixmap(pixmap)

    @property
    def size(self) -> QSizeF:
        """Sight size."""
        return self.__rect.rect().size()

    @size.setter
    def size(self, value: QSizeF):
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
        logging.getLogger("laserstudio").info(f"Move to position {x, y}")

        if self.stage is not None:
            self.stage.move_to(self.stage_coords_from_scene_coords(position), wait=True)
        else:
            self.setPos(position)

    def update_pos(self, position: Optional[Vector] = None):
        """Update Widget position according to the stage's position, received in parameter

        :param position: The stage's current position.
        """
        if position is None and self.stage is not None:
            position = self.stage.position
        if position is None:
            return
        scene_pos = self.scene_coords_from_stage_coords(position)
        self.setPos(scene_pos)

    def setPos(self, *args, **kwargs):
        """To make sure that the position of the stagesight is signaled
        at each change we override the setPos function.

        :param value: the final position of the widget"""
        if len(args) >= 1 and isinstance(pos := args[0], QPointF):
            pass
        elif isinstance(pos := kwargs.get("pos", None), QPointF):
            pass
        else:
            raise TypeError("Only QPointF are allowed")
        super(QGraphicsItemGroup, self).setPos(pos)
        self.position_changed.emit(pos)

    @property
    def position_changed(self) -> pyqtBoundSignal:
        """Convenient access to the position_changed signal from proxy object"""
        return self.__object.position_changed

    @property
    def distortion(self) -> QTransform:
        return self.image_group.transform()

    @distortion.setter
    def distortion(self, transform: Optional[QTransform]):
        self.resetTransform()
        self.image_group.resetTransform()
        if transform is not None:
            self.image_group.setTransform(transform)
            # The transform may induce a final translation
            # which can be measured by mapping the origin
            # and corrected by setting the image_group's position.
            mapped_origin = transform.map(QPointF(0.0, 0.0))
            dx, dy = mapped_origin.x(), mapped_origin.y()
            self.image_group.setPos(-dx, -dy)
        self.__update_size(self.size)

    def marker(
        self,
        marker_type: Union[type[LaserInstrument], type[ProbeInstrument]],
        index: int,
    ) -> Optional[ProbeMarker]:
        if marker_type not in [LaserInstrument, ProbeInstrument]:
            return None
        index += 1
        # Go through all markers, count for each matching types
        for marker in self._probe_markers:
            if LaserInstrument == marker_type:
                if isinstance(marker.probe, LaserInstrument):
                    index -= 1
            elif ProbeInstrument == marker_type:
                if type(marker.probe) is ProbeInstrument:
                    index -= 1
            if index == 0:
                return marker
        return None
