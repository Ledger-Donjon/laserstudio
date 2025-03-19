from .instrument import Instrument


class LightInstrument(Instrument):
    @property
    def light(self) -> bool:
        return False

    @light.setter
    def light(self, value: bool): ...

    @property
    def intensity(self):
        return 0.0

    @intensity.setter
    def intensity(self, value: float): ...
