from laserstudio.lsapi import LSAPI
import numpy
from typing import cast

def test_get_accumulated_image():
    api = LSAPI()
    image = api.accumulated_image(None)
    assert image is not None
    image = cast(numpy.ndarray, image)
    assert isinstance(image, numpy.ndarray)
