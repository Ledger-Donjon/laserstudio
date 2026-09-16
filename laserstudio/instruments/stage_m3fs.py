from __future__ import annotations

from pystages import M3FS

from .stage import StageInstrument


class M3FSStageInstrument(StageInstrument):
    """Class to regroup M3FS stage instrument operations"""

    # The base class picks the device from the configured type; declaring it
    # here just narrows it for this subclass (a property would shadow the
    # attribute the base constructor assigns).
    stage: M3FS
