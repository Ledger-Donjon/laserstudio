#!/usr/bin/python3
from .laserstudio import LaserStudio
from PyQt6.QtWidgets import QApplication, QStyleFactory
from PyQt6.QtGui import QPalette, QColor, QIcon
from PyQt6.QtCore import QLocale, Qt
import sys
import yaml
import os.path
import logging
import argparse
from .utils.util import resource_path
from .utils.colors import LedgerColors


def main():
    app = QApplication(sys.argv)

    parser = argparse.ArgumentParser(prog="laserstudio")
    parser.add_argument(
        "--log", choices=list(logging._nameToLevel.keys()), required=False
    )
    parser.add_argument("--conf_file", type=open, required=False)
    args = parser.parse_args()

    if args.log is not None:
        try:
            logging.basicConfig(level=logging.NOTSET)
            logger = logging.getLogger("laserstudio")
            logger.setLevel(args.log)
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
    app.setWindowIcon(QIcon(resource_path(":/icons/logo.svg")))
    app.setStyle(QStyleFactory.create("Fusion"))
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.Base, QColor(50, 50, 50))
    palette.setColor(QPalette.ColorRole.AlternateBase, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.lightGray)
    palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, QColor(30, 30, 30)
    )
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(200, 200, 200))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(100, 100, 100),
    )
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Highlight, LedgerColors.SafetyOrange.value)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)
    app.setStyleSheet("QToolBar { "
        "border: 1px solid #252525;"
        "border-radius: 4px;"
        "margin: 3px;"
        "padding: 6px;"
        "background-color: #252525 }")

    QLocale.setDefault(QLocale.c())

    win = LaserStudio(yaml_config)
    win.setWindowTitle(app.applicationDisplayName())
    win.show()
    return app.exec()


if __name__ == "__main__":
    main()
