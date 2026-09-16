from laserstudio.lsapi import LSAPI
import numpy
import pytest
from typing import cast

pytestmark = pytest.mark.integration

def test_get_accumulated_image():
    api = LSAPI()
    image = api.accumulated_image(None)
    assert image is not None
    image = cast(numpy.ndarray, image)
    assert isinstance(image, numpy.ndarray)
