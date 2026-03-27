#!/usr/bin/python3
from __future__ import annotations
from typing import cast
from ..utils.yaml_types import Config
import serial.tools.list_ports
import serial


class ChecksumError(Exception):
    """Thrown if a communication checksum error is detected."""


class ProtocolError(Exception):
    """Thrown if an unexpected response from the device is received."""


class ConnectionFailure(Exception):
    """Thrown if a connection to the device cannot be established."""


class DeviceSearchError(Exception):
    """Thrown if a device is not found with the given criteria."""

    def __init__(
        self,
        sn: str | None = None,
        vid_pid: tuple[str, str] | None = None,
        location: str | None = None,
        dev: str | None = None,
    ):
        self.sn = sn
        if vid_pid is not None and vid_pid[0] is not None:
            self.vid_pid: tuple[str, str] | None = vid_pid
        else:
            self.vid_pid = None
        self.location = location
        self.dev = dev

    def __str__(self) -> str:
        desc: list[str] = []
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
    """Thrown if no device is found with the given criteria."""

    def __str__(self) -> str:
        return (
            f"Error: No device found with the following criteria: {super().__str__()}"
        )


class MultipleDeviceFound(DeviceSearchError):
    """Thrown if multiple devices are found with the given criteria."""

    def __str__(self) -> str:
        return f"Error: Multiple devices found with the following criteria: {super().__str__()}"


def get_serial_device(config: str | Config) -> str:
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
        possible_matches: list[str] = []
        sn = None
        vid, pid = None, None
        location = None
        for port in serial.tools.list_ports.comports():
            match_sn = match_vid_pid = match_location = None
            if "sn" in config:
                sn = cast(str, config["sn"])
                match_sn = (sn == port.serial_number) or (port.device.endswith(sn))
            if "vid" in config and "pid" in config:
                if not isinstance(config["vid"], str) or not isinstance(
                    config["pid"], str
                ):
                    raise ValueError(
                        "In configuration file, 'vid' and 'pid' must be strings "
                        "in hexadecimal format (eg. '1234', 'ABCD')"
                    )
                vid = config["vid"]
                pid = config["pid"]
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
