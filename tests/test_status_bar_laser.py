"""The bottom status bar must follow the real state of the lasers."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PyQt6.QtWidgets import QApplication

from laserstudio.instruments.instruments import Instruments
from laserstudio.laserstudio_refonte import LaserStudioRefonte


@pytest.fixture(scope="module")
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def _make_window(lasers_on: list[bool]) -> tuple[LaserStudioRefonte, Instruments]:
    instruments = Instruments(
        {
            "lasers": [
                {"type": "Dummy", "label": f"L{i}"} for i in range(len(lasers_on))
            ]
        }
    )
    for laser, on in zip(instruments.lasers, lasers_on):
        laser.on_off = on
    return LaserStudioRefonte(instruments), instruments


@pytest.fixture
def windows() -> Iterator[list[LaserStudioRefonte]]:
    opened: list[LaserStudioRefonte] = []
    yield opened
    for window in opened:
        window.close()


def _laser_text(window: LaserStudioRefonte) -> str:
    return window._status_bar._laser.text()


@pytest.mark.parametrize(
    "lasers_on, expected",
    [
        ([], "LASER SAFE"),
        ([False], "LASER SAFE"),
        ([True], "LASER ARMED"),
        ([False, True], "LASER ARMED"),
    ],
)
def test_the_bar_shows_the_state_of_the_lasers_at_startup(
    app: QApplication,
    windows: list[LaserStudioRefonte],
    lasers_on: list[bool],
    expected: str,
) -> None:
    window, _ = _make_window(lasers_on)
    windows.append(window)
    assert _laser_text(window) == expected


def test_the_bar_follows_the_lasers_being_switched(
    app: QApplication, windows: list[LaserStudioRefonte]
) -> None:
    window, instruments = _make_window([False, False])
    windows.append(window)
    first, second = instruments.lasers

    first.on_off = True
    assert _laser_text(window) == "LASER ARMED"
    assert window.laser_armed is True

    # Still armed: the other laser is on.
    second.on_off = True
    first.on_off = False
    assert _laser_text(window) == "LASER ARMED"

    second.on_off = False
    assert _laser_text(window) == "LASER SAFE"
    assert window.laser_armed is False
