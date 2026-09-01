from laserstudio.instruments.camera import parse_objectives


def test_parse_objectives_uses_default_when_missing():
    assert parse_objectives({}, [1.0, 5.0]) == [1.0, 5.0]


def test_parse_objectives_from_config():
    assert parse_objectives({"objectives": [5, 10, 20.5]}, [1.0]) == [5.0, 10.0, 20.5]


def test_parse_objectives_ignores_invalid_and_falls_back():
    assert parse_objectives({"objectives": []}, [1.0, 5.0]) == [1.0, 5.0]
    assert parse_objectives({"objectives": ["x", 0, -2]}, [1.0]) == [1.0]
    assert parse_objectives({"objectives": "5,10"}, [1.0]) == [1.0]
