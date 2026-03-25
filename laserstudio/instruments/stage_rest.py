from __future__ import annotations

from typing import cast, TYPE_CHECKING
from pystages import Stage
from .rest_instrument import RestInstrument

if TYPE_CHECKING:
    from .stage import Vector


class StageRest(RestInstrument, Stage):
    """Class to implement REST stages"""

    def __init__(self, config: dict):
        """
        :param config: YAML configuration object
        """
        Stage.__init__(self)
        RestInstrument.__init__(self, config)
        self.api_command = cast(str, config.get("api_command", "position"))

        # Try a communication, will raise if the connection cannot be
        # done
        self._num_axis = len(self.position.data)

    @property
    def position(self) -> Vector:
        position = self.get().json().get("pos", [])
        from .stage import Vector as LSVector

        return LSVector(*position)

    @position.setter
    def position(self, value: Vector):
        self.post({"pos": value.data})

    @property
    def is_moving(self) -> bool:
        return self.get().json().get("moving", False)

    @property
    def num_axis(self) -> int:
        return self._num_axis
