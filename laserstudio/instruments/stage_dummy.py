from __future__ import annotations

from pystages import Stage, Vector
from typing import cast, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .stage import StageInstrument


class StageDummy(Stage):
    """Class to implement Dummy Stage"""

    def __init__(self, config: dict[str, Any], stage_instrument: StageInstrument):
        """
        :param config: YAML configuration object
        :param stage_instrument: The StageInstrument the Stage is attached to.
        """
        super().__init__(num_axis=cast(int, config.get("num_axis", 2)))
        from .stage import Vector as LSVector

        self._position: Vector = LSVector(dim=self.num_axis)
        self.stage_instrument = stage_instrument

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
