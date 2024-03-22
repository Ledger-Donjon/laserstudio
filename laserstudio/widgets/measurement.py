from .marker import Marker
from PyQt6.QtGui import QColorConstants


class Measurement(Marker):
    """Measurments are Markers with a specific ID. It is used as points to be added by the user and shown in the main viewer."""

    ID = 1

    def __init__(self, parent=None, color=QColorConstants.Red) -> None:
        super().__init__(parent, color=QColorConstants.Transparent, fillcolor=color)
        self._id = Measurement.ID
        Measurement.ID += 1

    @property
    def id(self):
        """Id of the Marker, as an integer."""
        return self._id

    def update_tooltip(self):
        """The tooltip of the measurement gives its position and its ID."""
        self.setToolTip(
            f"M{self.id}:[{', '.join(['{:.2f}'.format(x) for x in (self.pos().x(), self.pos().y())])}]"
        )
