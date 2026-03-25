from laserstudio.lsapi import LSAPI
import numpy
import pytest
from typing import Any, cast


def test_go_next():
    api = LSAPI()
    api.go_next()


def test_get_settings():
    api = LSAPI()
    assert api.instrument_settings("test") is not None
    assert api.instrument_settings("test2") is None


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
    result = cast(dict[str, Any], api.go_to_position(partial))
    assert "error" not in result
    assert "pos" in result
    new_pos = cast(list[float], result["pos"])
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
    response = api.send("motion/position", {"pos": too_long}, is_put=True)
    assert response.status_code == 400
    result = cast(dict[str, Any], response.json())
    assert "error" in result
    assert "pos" in result
    final_pos = cast(list[float], result["pos"])
    tolerance = 1e-6
    assert len(final_pos) == len(current)
    for i, value in enumerate(current):
        assert abs(final_pos[i] - value) <= tolerance
    
