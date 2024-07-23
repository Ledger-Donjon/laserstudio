from PyQt6.QtWidgets import QToolBar


class LaserToolbar(QToolBar):
    def __init__(self, title: str, object_name: str):
        """
        :param title: Toolbar title, as displayed in the context menus.
        :param object_name: Unique object name for Qt, used for settings save and restore.
        """
        super().__init__(title)
        super().setObjectName(object_name)  # For settings save and restore
