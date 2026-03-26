from hyshlr import HyshLR, NoDongleError, MultipleDongleError
from .light import LightInstrument
from .list_serials import get_serial_device
import logging
from ..utils.yaml_types import Config


class HayashiLRInstrument(LightInstrument):
    def __init__(self, config: Config):
        super().__init__(config=config)
        self.label = str(config.get("label", "Hayashi Light"))
        dev = config.get("dev")

        if dev == "":
            dev = None

        if isinstance(dev, dict) or isinstance(dev, str):
            dev = get_serial_device(dev)
        else:
            dev = None

        try:
            self.hyslr = HyshLR(dev)
        except MultipleDongleError:
            logging.getLogger("laserstudio").error(
                msg := "Multiple Hayashi Light dongles found."
                " Please specify the serial port explicitely."
            )
            raise MultipleDongleError(msg)
        except NoDongleError:
            logging.getLogger("laserstudio").error(
                msg
                := "No Hayashi Light dongle found. Please ensure the dongle is connected."
            )
            raise NoDongleError(msg)

    @property
    def light(self):
        return bool(self.hyslr.lamp)

    @light.setter
    def light(self, value: bool):
        self.hyslr.lamp = value

    @property
    def intensity(self):
        return self.hyslr.intensity

    @intensity.setter
    def intensity(self, value: float):
        self.hyslr.intensity = value

    @property
    def burnout(self):
        return self.hyslr.burnout
