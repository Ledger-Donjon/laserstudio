from .instrument import Instrument
from typing import Any


class LightInstrument(Instrument):
    """
    A Light Instrument, used to control the state and the intensity of a light source.
    """

    @property
    def light(self) -> bool:
        """
        Whether the light is on.
        """
        return False

    @light.setter
    def light(self, value: bool):
        """
        Set the light to on or off.
        """

    @property
    def intensity(self) -> float:
        """
        The intensity of the light in range [0.0, 1.0].
        """
        return 0.0

    @intensity.setter
    def intensity(self, value: float):
        """
        Set the intensity of the light in range [0.0, 1.0].
        """

    @property
    def settings(self) -> dict[str, Any]:
        """
        The settings of the light instrument include the intensity and the light state.
        """
        super_settings = super().settings
        super_settings["intensity"] = self.intensity
        super_settings["light"] = self.light
        return super_settings

    @settings.setter
    def settings(self, data: dict[str, Any]):
        """
        Set the settings of the light instrument.
        """
        Instrument.settings.__set__(self, data)
        if "light" in data:
            self.intensity = data["light"]
            self.parameter_changed.emit("light", data["light"])

        if "intensity" in data:
            self.intensity = data["intensity"]
            self.parameter_changed.emit("intensity", data["intensity"])
