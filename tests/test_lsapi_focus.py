from laserstudio.lsapi import LSAPI


def test_autofocus_register():
    api = LSAPI()
    api.autofocus()


def test_magicfocus():
    api = LSAPI()
    api.magicfocus()
