from __future__ import annotations

import logging

from PyQt6.QtCore import pyqtSignal
from pystages import CNCError, CNCRouter

from ..utils.grbl_alarms import format_grbl_alarm_message
from .stage import StageInstrument


class CNCRouterStageInstrument(StageInstrument):
    """Class to regroup CNC router stage instrument operations"""

    # Signal emitted when the GRBL controller reports an alarm
    grbl_alarm = pyqtSignal(str)

    # The base class picks the device from the configured type; declaring it
    # here just narrows it for this subclass (a property would shadow the
    # attribute the base constructor assigns).
    stage: CNCRouter

    def _handle_cnc_error(self, error: CNCError, *, notify: bool = False) -> None:
        message = format_grbl_alarm_message(error)
        alarm_key = (error.status.substate, error.args[0] if error.args else "")
        if alarm_key != self._last_reported_alarm:
            self._last_reported_alarm = alarm_key
            logging.getLogger("laserstudio").warning(message)
            if notify:
                self.grbl_alarm.emit(message)

    def clear_grbl_alarm_state(self) -> None:
        """Clear the GRBL alarm state so position polling can resume after unlock."""
        self._last_reported_alarm = None
