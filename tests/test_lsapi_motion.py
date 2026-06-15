from laserstudio.lsapi import LSAPI, InstrumentNotFound, InvalidParameter
import numpy
import pytest
from typing import cast


def test_go_next():
    api = LSAPI()
    api.go_next()


def test_get_settings():
    api = LSAPI()
    assert api.instrument_settings("test") is not None
    with pytest.raises(InstrumentNotFound):
        api.instrument_settings("test2")


def test_set_settings():
    api = LSAPI()
    api.instrument_settings("test", {"settings": {"label": "TOTO"}})


def test_get_accumulated_image():
    api = LSAPI()
    image = api.accumulated_image(None)  # type: ignore
    assert image is not None
    assert isinstance(image, numpy.ndarray)



def test_go_to_position_shorter_coordinates():
    api = LSAPI()
    current = api.position()
    if not current or len(current) < 2:
        pytest.skip("Need at least 2 axes to test partial move")
    partial = list(current[:-1])
    partial[0] = float(partial[0]) + 1.0
    new_pos = api.go_to_position(partial)
    assert len(new_pos) == len(current)
    tolerance = 1e-6
    for i, value in enumerate(partial):
        assert abs(new_pos[i] - value) <= tolerance
    assert abs(new_pos[-1] - current[-1]) <= tolerance


def test_go_to_position_too_many_coordinates():
    api = LSAPI()
    current = api.position()
    if not current:
        pytest.skip("No stage available")
    new_pos = list(current)
    new_pos[0] += 1.0
    too_long = new_pos + [0.0]
    with pytest.raises(InvalidParameter) as excinfo:
        api.go_to_position(too_long)
    error = excinfo.value
    assert error.status_code == 400
    final_pos = cast(list[float], error.details["pos"])
    tolerance = 1e-6
    assert len(final_pos) == len(current)
    for i, value in enumerate(current):
        assert abs(final_pos[i] - value) <= tolerance
    
