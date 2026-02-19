from .chipscan import ChipScan
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QLocale
import sys
from ..colors import LedgerPalette, LedgerStyle, ledger_stylesheet
import yaml


def main():
    app = QApplication(sys.argv)

    app.setApplicationName("Chip Scan")
    app.setApplicationDisplayName("Chip Scan")
    app.setStyle(LedgerStyle)
    app.setPalette(LedgerPalette)
    app.setStyleSheet(ledger_stylesheet())

    QLocale.setDefault(QLocale.c())
    with open("config.yaml") as stream:
        yaml_config = yaml.load(stream, yaml.FullLoader)
    win = ChipScan(yaml_config)
    win.setWindowTitle("Chip Scan")
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
