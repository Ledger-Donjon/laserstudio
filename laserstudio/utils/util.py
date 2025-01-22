import os
from PyQt6.QtGui import QTransform, QPixmap, QColor
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtCore import Qt
from typing import Union
from .colors import LedgerColors
import yaml

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


def qtransform_to_yaml(transform: QTransform):
    """:return: Dict for yaml serialization from a QTransform."""
    result = {}
    for i in range(1, 4):
        for j in range(1, 4):
            result[f"m{i}{j}"] = transform.__getattribute__(f"m{i}{j}")()
    return result


def yaml_to_qtransform(dict: dict):
    items = []
    for i in range(1, 4):
        for j in range(1, 4):
            items.append(float(dict[f"m{i}{j}"]))
    return QTransform(*items)


def colored_image(
    path: str,
    color: Union[QColor, Qt.GlobalColor, int, LedgerColors] = Qt.GlobalColor.lightGray,
    mask_color: Union[QColor, Qt.GlobalColor, int] = Qt.GlobalColor.black,
) -> QPixmap:
    """Load an image, use it as a mask and create a Pixmap colored with given color"""
    pixmap = QPixmap(resource_path(path))
    mask = pixmap.createMaskFromColor(mask_color, Qt.MaskMode.MaskOutColor)
    if isinstance(color, LedgerColors):
        color = color.value
    pixmap.fill(color)
    pixmap.setMask(mask)
    return pixmap


def save_configuration_file(config: dict):
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
