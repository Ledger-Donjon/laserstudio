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

    @property
    def settings(self) -> dict:
        super_settings = super().settings
        super_settings["intensity"] = self.intensity
        super_settings["light"] = self.light
        return super_settings

    @settings.setter
    def settings(self, data: dict):
        super().settings = data
        if "light" in data:
            self.intensity = data["light"]
            self.parameter_changed.emit("light", data["light"])

        if "intensity" in data:
            self.intensity = data["intensity"]
            self.parameter_changed.emit("intensity", data["intensity"])
