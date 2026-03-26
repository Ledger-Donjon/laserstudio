from .stage import Tic, TicDirection, Vector
from .instrument import Instrument
from ..utils.yaml_types import Config


class ShutterInstrument(Instrument):
    """
    A Shutter Instrument, used to open and close
    the view of a camera or a light source.
    """

    def __init__(self, config: Config):
        """
        Initialize the shutter instrument.
        The shutter is considered open by default.
        """
        super().__init__(config=config)
        self.__open = True  # Open by default

    @property
    def open(self) -> bool:
        """
        Whether the shutter is open (eg camera can acquire images, light source is on...).
        """
        return self.__open

    @open.setter
    def open(self, value: bool):
        """
        Set the shutter to open or closed.
        """
        if not isinstance(value, bool):
            raise ValueError("Expected bool")
        self.__open = value

    @property
    def settings(self) -> Config:
        """
        The settings of the shutter instrument include the open state.
        """
        super_settings = super().settings
        super_settings["open"] = self.open
        return super_settings

    @settings.setter
    def settings(self, data: Config):
        """
        Set the settings of the shutter instrument.
        """
        Instrument.settings.__set__(self, data)  # type: ignore[attr-defined]
        if "open" in data and isinstance(data["open"], bool):
            self.open = data["open"]
            self.parameter_changed.emit("open", data["open"])


class TicShutterInstrument(ShutterInstrument):
    """
    A shutter instrument that uses a Tic stage to open and close.
    """

    def __init__(self, config: Config):
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
        ShutterInstrument.open.__set__(self, value)  # type: ignore[attr-defined]
        if value != self.__open:
            self.tic.position = Vector({False: -106, True: 0}[value])
        self.__open = value
