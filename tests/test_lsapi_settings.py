from laserstudio.lsapi import LSAPI

def test_get_settings():
    api = LSAPI()
    settings = api.instrument_settings("Dummy Probe")
    assert settings is not None
    assert settings["label"] == "Dummy Probe"
    assert settings["offset_pos"] == [0, 0]


def test_set_settings():
    api = LSAPI()
    api.instrument_settings("Dummy Probe", {"settings": {"label": "TOTO"}})
    settings = api.instrument_settings("Dummy Probe")
    assert settings is not None
    assert settings["label"] == "TOTO"
