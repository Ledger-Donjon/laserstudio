#!/usr/bin/python3
from .laserstudio import LaserStudio
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QLocale
import sys
import yaml
import os.path
import logging
import argparse
from .utils.util import resource_path
from .utils.colors import LedgerPalette, LedgerStyle
from .config_generator import ConfigGenerator, ConfigGeneratorWizard


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
    app.setStyle(LedgerStyle)
    app.setPalette(LedgerPalette)
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
        config_generator = ConfigGenerator()
        sys.argv.append("-L")
        config_generator.get_flags()
        config_generator.load_schema()

        wizard = ConfigGeneratorWizard(config_generator.schema)
        wizard.exec()
        # config_generator.print_intro()
        # yaml_config = config_generator.generate_json_interactive()
        # assert yaml_config is None or type(yaml_config) is dict

    win = LaserStudio(yaml_config)
    win.setWindowTitle(app.applicationDisplayName())
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
