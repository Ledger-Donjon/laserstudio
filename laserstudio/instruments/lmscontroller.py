from pylmscontroller import LMSController
from .shutter import ShutterInstrument
from .light import LightInstrument


class LMSControllerInstrument(ShutterInstrument, LightInstrument):
    def __init__(self, config: dict):
        super(ShutterInstrument, self).__init__(config)
        super(LightInstrument, self).__init__(config)
        print(f"INSTANCIATION OF LMS CONTOLLER WITH config {config}")
        self.open = False

    # Shutter operations
    # @property
    # def open(self):
    #     return super(ShutterInstrument, self).open

    # @open.setter
    # def open(self, value: bool):
    #     super(ShutterInstrument, self).open = self
