from PyQt6.QtCore import QObject, pyqtSignal, QVariant


class Instrument(QObject):
    # Signal emitted when the instrument has a parameter which changed in another way than UI interface
    parameter_changed = pyqtSignal(str, QVariant)

    def __init__(self, config: dict):
        super().__init__()
        self.label: str | None = config.get("label")

    @property
    def settings(self) -> dict:
        """Export settings to a dict for yaml serialization."""
        # Label is not actually a setting but more an identifier
        if self.label is not None:
            return {"label": self.label}
        else:
            return {}

    @settings.setter
    def settings(self, data: dict):
        """Import settings from a dict."""
        if data.get("label") != self.label:
            print(
                "Warning, we are applying settings for a device "
                + f"with a different label ({self.label}), "
                + "from a file created with device having different "
                + f"label ({data.get('label')})."
            )
        return
