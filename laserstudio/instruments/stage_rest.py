from pystages import Stage, Vector
from .rest_instrument import RestInstrument


class StageRest(RestInstrument, Stage):
    """Class to implement REST stages"""

    def __init__(self, config: dict):
        """
        :param config: YAML configuration object
        """
        Stage.__init__(self)
        RestInstrument.__init__(self, config)

        # Try a communication, will raise if the connection cannot be
        # done
        self._num_axis = len(self.position.data)

    @property
    def position(self) -> Vector:
        position = self.get().json().get("pos", [])
        return Vector(*position)

    @position.setter
    def position(self, value: Vector):
        self.post({"pos": value.data})

    @property
    def is_moving(self) -> bool:
        return self.get().json().get("moving", False)

    @property
    def num_axis(self) -> int:
        return self._num_axis
