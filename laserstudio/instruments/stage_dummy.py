from pystages import Stage, Vector
from typing import cast, TYPE_CHECKING

if TYPE_CHECKING:
    from .stage import StageInstrument


class StageDummy(Stage):
    """Class to implement Dummy Stage"""

    def __init__(self, config: dict, stage_instrument: "StageInstrument"):
        """
        :param config: YAML configuration object
        :param stage_instrument: The StageInstrument the Stage is attached to.
        """
        super().__init__(num_axis=cast(int, config.get("num_axis", 2)))
        self._position = Vector(dim=self.num_axis)
        self.stage_instrument = stage_instrument

    @property
    def position(self) -> Vector:
        return self._position

    @position.setter
    def position(self, value: Vector):
        self._position = value
        self.stage_instrument.refresh_stage()

    @property
    def is_moving(self) -> bool:
        return False
