from __future__ import annotations
from typing import Any
import yaml
import os
from PyQt6.QtGui import (
    QTransform,
    QPixmap,
    QColor,
    QPen,
    QPainter,
    QIcon,
    QPainterPath,
)
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtCore import Qt, QPointF, QRectF, QSize
from PyQt6.QtCharts import QChartView
from .colors import LedgerColors
from ..utils.yaml_types import Config

__dirname = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def resource_path(path: str) -> str:
    """
    Transforms a .":/path/to/file" path to the relative path from the main script

    :param path: The path to resolve.
    :return: A string representing the path.
    """
    if not path.startswith(":/"):
        return path
    return os.path.join(__dirname, path[2:])


def qtransform_to_yaml(transform: QTransform) -> Config:
    """:return: Dict for yaml serialization from a QTransform."""
    result: Config = {}
    for i in range(1, 4):
        for j in range(1, 4):
            result[f"m{i}{j}"] = transform.__getattribute__(f"m{i}{j}")()
    return result


def yaml_to_qtransform(dict: Config) -> QTransform:
    items: list[float] = []
    for i in range(1, 4):
        for j in range(1, 4):
            value = dict[f"m{i}{j}"]
            if not isinstance(value, (float, int)):
                raise ValueError(f"Value {value} is not a float or int")
            items.append(float(value))
    return QTransform(*items)


def colored_image(
    path: str,
    color: QColor | Qt.GlobalColor | int | LedgerColors = Qt.GlobalColor.lightGray,
    mask_color: QColor | Qt.GlobalColor | int = Qt.GlobalColor.black,
) -> QPixmap:
    """Load an image, use it as a mask and create a Pixmap colored with given color"""
    pixmap = QPixmap(resource_path(path))
    mask = pixmap.createMaskFromColor(mask_color, Qt.MaskMode.MaskOutColor)
    if isinstance(color, LedgerColors):
        color = color.value
    pixmap.fill(color)
    pixmap.setMask(mask)
    return pixmap


def save_configuration_file(config: dict[str, Any]):
    """
    Save the configuration file.
    """
    default_file_name = "config.yaml"

    # Open a file dialog to select the file to save the configuration
    file_name, _ = QFileDialog.getSaveFileName(
        None,
        "Save Configuration File",
        default_file_name,
        "YAML Files (*.yaml);;All Files (*)",
        options=QFileDialog.Option.DontUseNativeDialog,
    )

    # If a file name was selected
    if file_name:
        try:
            # Save the configuration to the file
            with open(file_name, "w") as file:
                yaml.dump(config, file, indent=2)
            QMessageBox.information(
                None, "Success", f"Configuration saved to {file_name}"
            )
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to save configuration: {e}")


class ChartViewWithVMarker(QChartView):
    _x: float | None = None

    @property
    def vmarker(self):
        return self._x

    @vmarker.setter
    def vmarker(self, x: float | None):
        self._x = x
        self.update()

    def drawForeground(self, painter: QPainter | None, rect: QRectF):
        if (c := self.chart()) is None or painter is None or self.vmarker is None:
            super().drawForeground(painter, rect)
            return
        painter.save()
        pen = QPen(LedgerColors.Grellow.value)
        pen.setWidth(3)
        painter.setPen(pen)
        p = c.mapToPosition(QPointF(self.vmarker, 0))
        r = c.plotArea()
        p1 = QPointF(p.x(), r.top())
        p2 = QPointF(p.x(), r.bottom())
        painter.drawLine(p1, p2)
        painter.restore()


def create_color_qicon(
    color: QColor | Qt.GlobalColor | int | LedgerColors, size: int = 16
) -> QIcon:
    """
    Create a circle icon of a given color.
    :param color: Color to create the icon from.
    :return: Icon.
    """
    if isinstance(color, LedgerColors):
        color = color.value
    if isinstance(color, Qt.GlobalColor):
        color = QColor(color)
    if isinstance(color, int):
        color = QColor(color)

    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHints(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addEllipse(size / 2 - 3, size / 2 - 3, 6, 6)
    painter.fillPath(path, QColor(0, 0, 0, 100))
    path = QPainterPath()
    path.addEllipse(size / 2 - 7, size / 2 - 7, 14, 14)
    painter.setPen(QPen(Qt.GlobalColor.black, 1))
    painter.fillPath(path, color)
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)
