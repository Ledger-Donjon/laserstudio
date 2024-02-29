import os
from PyQt6.QtGui import QTransform

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
