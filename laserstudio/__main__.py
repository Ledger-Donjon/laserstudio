#!/usr/bin/python3
from __future__ import annotations
import argparse
import logging
import os.path
import pathlib
import sys
import yaml

from PyQt6.QtCore import QLocale
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from .config_generator import ConfigGenerator, ConfigGeneratorWizard
from .laserstudio import LaserStudio
from .utils.util import resource_path
from .utils.colors import LedgerPalette, LedgerStyle, ledger_stylesheet
from .instruments.list_serials import list_devices
from .utils.yaml_types import Config


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("laserstudio")


def main() -> int:
    app = QApplication(sys.argv)

    parser = argparse.ArgumentParser(prog="laserstudio")
    parser.add_argument(
        "--log",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        default="INFO",
    )
    parser.add_argument(
        "--config",
        type=pathlib.Path,
        required=False,
        default=os.path.join(os.getcwd(), "config.yaml"),
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        required=False,
        default=False,
    )
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        return 0
    logger.setLevel(args.log)

    app.setApplicationName("Laser Studio")
    app.setApplicationDisplayName("Laser Studio")
    app.setWindowIcon(QIcon(resource_path(":/icons/logo.svg")))
    app.setStyle(LedgerStyle)
    app.setPalette(LedgerPalette)
    app.setStyleSheet(ledger_stylesheet())

    QLocale.setDefault(QLocale.c())

    # Loading configuration file
    stream = None
    try:
        stream = open(args.config, "r")
    except FileNotFoundError:
        logger.error(f"Configuration file {args.config} not found")
    except Exception as e:
        logger.error(
            f"Encountered error while opening configuration file {args.config}: {e}"
        )

    yaml_config: Config | None = None
    if stream is not None:
        # Load the found or given configuration file
        try:
            yaml_config = yaml.safe_load(stream)
        except Exception as e:
            logger.error(
                f"Encountered error while loading configuration file {args.config}: {e}"
            )

        # Check if the configuration file is valid
        if type(yaml_config) is not dict:
            logger.error("Invalid configuration file: it is not a dictionary")
            yaml_config = None
        else:
            logger.info(f"Configuration file {args.config} loaded successfully")

    if yaml_config is None:
        # No configuration file found, generate one
        config_generator = ConfigGenerator()
        sys.argv.append("-L")  # Force to load the schema from the local files
        config_generator.get_flags()
        config_generator.load_schema()

        wizard = ConfigGeneratorWizard(config_generator.schema)
        wizard.exec()
        yaml_config = wizard.config_result_page.config
        logger.info("Configuration generated successfully")

    win = LaserStudio(yaml_config)
    win.setWindowTitle(app.applicationDisplayName())
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
