from typing import Any
from PyQt6.QtCore import QObject, pyqtSignal, QVariant
from ..utils.yaml_types import Config


class Instrument(QObject):
    # Signal emitted when the instrument has a parameter which changed in another way than UI interface
    parameter_changed = pyqtSignal(str, QVariant)

    def __init__(self, config: dict[str, Any]):
        super().__init__()
        self.label: str | None = config.get("label")

    @property
    def settings(self) -> Config:
        """Export settings to a dict for yaml serialization."""
        # Label is not actually a setting but more an identifier
        if self.label is not None:
            return {"label": self.label}
        else:
            return {}

    @settings.setter
    def settings(self, data: Config):
        """Import settings from a dict."""
        if data.get("label") != self.label:
            print(
                "Warning, we are applying settings for a device "
                + f"with a different label ({self.label}), "
                + "from a file created with device having different "
                + f"label ({data.get('label')})."
            )
        return

    def set_log_level(self, level: int) -> None:
        """Propagate the application log level to instrument-specific loggers."""
        return
