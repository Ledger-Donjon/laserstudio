#!/usr/bin/python3
from typing import Union, cast
import serial.tools.list_ports
import serial


class ChecksumError(Exception):
    """Thrown if a communication checksum error is detected."""

    pass


class ProtocolError(Exception):
    """Thrown if an unexpected response from the device is received."""

    pass


class ConnectionFailure(Exception):
    pass


class DeviceSearchError(Exception):
    def __init__(self, sn=None, vid_pid=None, location=None, dev=None):
        self.sn = sn
        if vid_pid is not None and vid_pid[0] is not None:
            self.vid_pid = vid_pid
        else:
            self.vid_pid = None
        self.location = location
        self.dev = dev

    def __str__(self) -> str:
        desc = []
        if self.sn:
            desc += [f"sn {self.sn}"]
        if self.vid_pid:
            desc += [f"vid:pid {self.vid_pid[0]}:{self.vid_pid[1]}"]
        if self.location:
            desc += [f"location: {self.location}"]
        if self.dev:
            desc += [f"device path: {self.dev}"]
        return " ".join(desc)


class DeviceNotFoundError(DeviceSearchError):
    pass


class MultipleDeviceFound(DeviceSearchError):
    pass


def get_serial_device(config: Union[str, dict]):
    """
    Find serial device path given a configuration.
    :param config: Configuration from YAML file.
        If it is a string, it is directly the serial device path.
        Otherwise, it should be a dict with search filters,
        such as the serial number.
    """
    if isinstance(config, str):
        for port in serial.tools.list_ports.comports():
            if port.device == config:
                return config
        raise DeviceNotFoundError(dev=config)
    elif isinstance(config, dict):
        possible_matches = []
        sn = None
        vid, pid = None, None
        location = None
        for port in serial.tools.list_ports.comports():
            match_sn = match_vid_pid = match_location = None
            if "sn" in config:
                sn = cast(str, config["sn"])
                match_sn = (sn == port.serial_number) or (port.device.endswith(sn))
            if "vid" in config and "pid" in config:
                vid, pid = cast(str, config["vid"]), cast(str, config["pid"])
                match_vid_pid = (vid == f"{port.vid or 0:04X}") and (
                    pid == f"{port.pid or 0:04X}"
                )
            if "location" in config:
                location = cast(str, config["location"])
                match_location = (port.location or "").startswith(location)
            matches = [match_sn, match_vid_pid, match_location]
            # There should be at least one match, and only matches.
            if True in matches and False not in matches:
                possible_matches.append(port.device)
        if len(possible_matches) == 0:
            raise DeviceNotFoundError(sn=sn, vid_pid=(vid, pid), location=location)
        elif len(possible_matches) > 1:
            raise MultipleDeviceFound(sn=sn, vid_pid=(vid, pid))
        else:
            return possible_matches[0]
    else:
        raise ValueError("Invalid dev value")


def list_devices():
    for p in serial.tools.list_ports.comports():
        print(p)
        print(f" | sn: {p.serial_number}\n | info: {p.usb_info()}\n | path: {p.device}")


if __name__ == "__main__":
    list_devices()
