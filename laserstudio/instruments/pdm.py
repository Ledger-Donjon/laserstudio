from pypdm import ConnectionFailure, Link, PDM, SyncSource, DelayLineType, CurrentSource
from .list_serials import get_serial_device, DeviceSearchError
import logging
from .laser import LaserInstrument


class PDMInstrument(LaserInstrument):
    "PDM device links dict. Used for link sharing between different lasers."
    __PDM_LINKS = {}

    def __init__(self, config: dict):
        """
        :param config: YAML configuration object
        """
        super().__init__(config=config)

        # To refresh stage position in the view, in real-time
        self.refresh_interval = cast(Optional[int], config.get("refresh_interval_ms"))

        device_type = config.get("type")
        dev = config.get("dev")
        if dev is None:
            logging.getLogger("laserstudio").error(
                f"In configuration file, 'laser.dev' is mandatory for type {device_type}"
            )
            raise

        try:
            dev = get_serial_device(dev)
        except DeviceSearchError as e:
            logging.getLogger("laserstudio").error(
                f"Laser is enabled but {device_type} is not found: {str(e)}...  Skipping."
            )
            raise

        if dev in PDMInstrument.__PDM_LINKS:
            link = PDMInstrument.__PDM_LINKS[dev]
        else:
            logging.getLogger("laserstudio").info(
                f"Connecting to {device_type} {dev}... "
            )
            try:
                link = Link(dev)
                logging.getLogger("laserstudio").info("OK")
            except ConnectionFailure:
                logging.getLogger("laserstudio").info("Failed")
                raise
            PDMInstrument.__PDM_LINKS[dev] = link
        self.pdm = pdm = PDM(config["num"], link)
        # Switch off the laser as soon as possible
        logging.getLogger("laserstudio").debug("Deactivate laser")
        pdm.activation = False
        pdm.apply()
        # Set some default settings
        logging.getLogger("laserstudio").debug("Setting some default values")
        pdm.sync_source = SyncSource.EXTERNAL_TTL_LVTTL
        pdm.delay_line_type = DelayLineType.NONE
        pdm.current_source = CurrentSource.NUMERIC
        pdm.apply()
        logging.getLogger("laserstudio").debug("Finishing discussion with PDM")

        self._interlock_status = None
        if self.refresh_interval is not None:
            QTimer.singleShot(
                self.refresh_interval, Qt.TimerType.CoarseTimer, self.refresh_pdm
            )

    @property
    def interlock_status(self) -> bool:
        """Get the laser interlock status, emits a signal when it changes"""
        state = self.pdm.interlock_status
        if state != self._interlock_status:
            self._interlock_status = state
            self.parameter_changed.emit("interlock_status", QVariant(state))
            if state == True:
                # The interlock has been opened, it may have changed the state of the
                # activation
                _ = self.on_off
        return state
    
    @property
    def on_off(self):
        return self.pdm.activation

    @on_off.setter
    def on_off(self, value: bool):
        self.pdm.activation = value
        self.pdm.apply()
        assert LaserInstrument.on_off.fset is not None
        LaserInstrument.on_off.fset(self, value)

    @property
    def current_percentage(self) -> float:
        return self.pdm.current_percentage

    @current_percentage.setter
    def current_percentage(self, value: float):
        self.pdm.current_percentage = value
        self.pdm.apply()
        assert LaserInstrument.current_percentage.fset is not None
        LaserInstrument.current_percentage.fset(self, value)

    @property
    def offset_current(self) -> float:
        return self.pdm.offset_current

    @offset_current.setter
    def offset_current(self, value: float):
        self.pdm.offset_current = value
        self.pdm.apply()
        assert LaserInstrument.offset_current.fset is not None
        LaserInstrument.offset_current.fset(self, value)

    def __del__(self):
        # On deletion of the object, we force the deactivation of the PDM
        self.pdm.activation = False
        self.pdm.apply()

    def refresh_pdm(self):
        """Called regularly to get laser state which can change externally (interlock)"""
        _ = self.interlock_status

        if self.refresh_interval is not None:
            QTimer.singleShot(
                self.refresh_interval, Qt.TimerType.CoarseTimer, self.refresh_pdm
            )