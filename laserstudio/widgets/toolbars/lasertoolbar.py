from PyQt6.QtWidgets import QToolBar


class LaserToolbar(QToolBar):
    def __init__(self, title: str, laser_model: str, laser_num: int):
        """
        :param laser_model: Equipment model, such as "pdm". Used for settings save and restore.
        :param laser_num: Laser equipment index.
        """
        super().__init__(title)
        super().setObjectName(f"toolbox-laser-{laser_model}-{laser_num}")  # For settings save and restore
