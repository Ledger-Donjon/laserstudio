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
from .config_generator import ConfigGenerator


def main():
    app = QApplication(sys.argv)

    parser = argparse.ArgumentParser(prog="laserstudio")
    parser.add_argument(
        "--log", choices=list(logging._nameToLevel.keys()), required=False
    )
    parser.add_argument("--conf_file", type=argparse.FileType("r"), required=False)
    args = parser.parse_args()

    if args.log is not None:
        try:
            logging.basicConfig(level=logging.NOTSET)
            logger = logging.getLogger("laserstudio")
            logger.setLevel(args.log)
        except ValueError as e:
            print("Warning, error during setting log level:", e)
            pass

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
    app.setStyleSheet(
        "QToolBar { "
        "border: 1px solid #252525;"
        "border-radius: 4px;"
        "margin: 3px;"
        "padding: 6px;"
        "background-color: #252525 }"
    )

    QLocale.setDefault(QLocale.c())

    # Loading configuration file
    stream = None
    if args.conf_file is not None:
        stream = args.conf_file
    else:
        # Search existing configuration file
        current_dir = os.path.realpath((os.curdir))
        while not os.path.exists(os.path.join(current_dir, "config.yaml")):
            parent_dir = os.path.dirname(current_dir)
            if current_dir == parent_dir:
                break
            current_dir = parent_dir

        if os.path.exists(path := os.path.join(current_dir, "config.yaml")):
            stream = open(path, "r")

    if stream is not None:
        yaml_config = yaml.load(stream, yaml.FullLoader)
    else:
        config_generator = ConfigGenerator(
            base_url="/Volumes/Work/Gits/Ledger-Donjon/laserstudio/config_schema"
        )
        config_generator.load_schema()
        config_generator.print_intro()
        yaml_config = config_generator.generate_json_interactive()
        assert yaml_config is None or type(yaml_config) is dict

    win = LaserStudio(yaml_config)
    win.setWindowTitle(app.applicationDisplayName())
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
