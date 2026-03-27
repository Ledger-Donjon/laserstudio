from __future__ import annotations

from pystages import Stage, Vector
from ..utils.yaml_types import Config


class StageDummy(Stage):
    """Class to implement Dummy Stage"""

    def __init__(self, config: Config):
        """
        :param config: YAML configuration object
        """
        assert isinstance(config["num_axis"], int), "num_axis must be an integer"
        super().__init__(num_axis=config["num_axis"])
        from .stage import Vector as LSVector

        self._position: Vector = LSVector(dim=self.num_axis)

    @property
    def position(self) -> Vector:
        # Do not return the object itself, but a copy
        return Vector(*self._position.data)

    @position.setter
    def position(self, value: Vector):
        self._position = value

    @property
    def is_moving(self) -> bool:
        return False
