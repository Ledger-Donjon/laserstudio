from laserstudio.lsapi import LSAPI
import pytest

pytestmark = pytest.mark.integration


def test_autofocus_register():
    api = LSAPI()
    api.autofocus()


def test_magicfocus():
    api = LSAPI()
    api.magicfocus()
