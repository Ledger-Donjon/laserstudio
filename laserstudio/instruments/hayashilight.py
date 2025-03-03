from hyshlr import HyshLR, NoDongleError, MultipleDongleError
from .instrument import Instrument
from .list_serials import get_serial_device
import logging


class HayashiLRInstrument(Instrument):
    def __init__(self, config: dict):
        super().__init__(config=config)
        self.label = config.get("label", "Hayashi Light")
        dev = config.get("dev")
        if dev == "":
            dev = None

        if dev is not None:
            dev = get_serial_device(dev)

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
