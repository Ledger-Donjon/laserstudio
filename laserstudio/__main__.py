#!/usr/bin/python3
from .laserstudio import LaserStudio
from PyQt6.QtWidgets import QApplication, QStyleFactory
from PyQt6.QtGui import QPalette, QColor, QIcon
import sys
import yaml
import os.path
from .util import resource_path
import logging

if __name__ == "__main__":
    app = QApplication(sys.argv)

    for arg in sys.argv:
        if arg.startswith("--log="):
            level = arg[len("--log=") :]
            try:
                logging.basicConfig(level=level)
            except ValueError as e:
                print("Warning, error during setting log level:", e)
                pass

    # Get existing configuration file
    if os.path.exists("config.yaml"):
        yaml_config = yaml.load(open("config.yaml", "r"), yaml.FullLoader)
    else:
        yaml_config = None

    app.setApplicationName("Laser Studio")
    app.setApplicationDisplayName("Laser Studio")
    app.setWindowIcon(QIcon(resource_path(":/icons/logo.png")))
    app.setStyle(QStyleFactory.create("Fusion"))
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.Base, QColor(40, 40, 40))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Text, QColor(200, 200, 200))
    palette.setColor(QPalette.ColorRole.Button, QColor(40, 40, 40))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, QColor(30, 30, 30)
    )
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(200, 200, 200))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(100, 100, 100),
    )
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Link, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(40, 120, 233))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    win = LaserStudio(yaml_config)
    win.setWindowTitle(app.applicationDisplayName())
    win.show()
    sys.exit(app.exec())
