from pystages import Tic, TicDirection, Vector
from .instrument import Instrument


class ShutterInstrument(Instrument):
    def __init__(self, config: dict):
        super().__init__(config=config)
        self.__open = True  # Open by default

    @property
    def open(self) -> bool:
        return self.__open

    @open.setter
    def open(self, value: bool):
        if type(value) is not bool:
            raise ValueError("Expected bool")
        self.__open = value

    @property
    def settings(self) -> dict:
        super_settings = super().settings
        super_settings["open"] = self.open
        return super_settings

    @settings.setter
    def settings(self, data: dict):
        super().settings = data
        if "open" in data:
            self.open = data["open"]
            self.parameter_changed.emit("open", data["open"])


class TicShutterInstrument(ShutterInstrument):
    def __init__(self, config: dict):
        super().__init__(config=config)
        self.tic = Tic()
        self.tic.exit_safe_start()
        self.tic.go_home(TicDirection.FORWARD)
        self.__open = True  # Open after homing

    @property
    def open(self) -> bool:
        return super().open

    @open.setter
    def open(self, value: bool):
        super().open = value
        if value != self.__open:
            self.tic.position = Vector({False: -106, True: 0}[value])
