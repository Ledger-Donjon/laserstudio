from .chipscan import ChipScan
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QLocale
import sys
import argparse
import os.path
import subprocess
from ..util import resource_path
from ..colors import LedgerPalette, LedgerStyle
import yaml


def main():
    app = QApplication(sys.argv)
    parser = argparse.ArgumentParser(prog="chipscan")

    app.setApplicationName("Chip Scan")
    app.setApplicationDisplayName("Chip Scan")
    # app.setWindowIcon(QIcon(resource_path(":/icons/logo.svg")))
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
    with open("config.yaml") as stream:
        yaml_config = yaml.load(stream, yaml.FullLoader)
    win = ChipScan(yaml_config)
    win.setWindowTitle("Chip Scan")
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
