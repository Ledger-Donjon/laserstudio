from laserstudio.lsapi import LSAPI
from random import random


def test_add_measurement():
    api = LSAPI()
    m = api.measurement(
        (random(), random(), random(), 0.7), p := (random() * 100, random() * 100)
    )
    assert list(p) == m["pos"]


def test_add_5000_measurements_seq():
    api = LSAPI()
    first = api.measurement(
        (random(), random(), random(), 0.7), p := (random() * 100, random() * 100)
    )
    col_pos = [
        ((random(), random(), random(), 0.7), (random() * 100, random() * 100))
        for _ in range(1, 5000)
    ]

    markers = [api.measurement(color, pos) for (color, pos) in col_pos]

    for i, m in enumerate(markers):
        assert m["id"] == (1 + i) + first["id"]


def test_add_5000_measurements_batch_by100():
    api = LSAPI()
    for _ in range(50):
        first = api.measurement(
            (random(), random(), random(), 0.7), (random() * 100, random() * 100)
        )
        positions = [(random() * 100, random() * 100) for _ in range(1, 100)]
        color = (random(), random(), random(), 0.7)
        markers = api.measurement(color, positions)

        for i, m in enumerate(markers["markers"]):
            assert m["id"] == (1 + i) + first["id"]


def test_add_5000_measurements_in_one():
    api = LSAPI()
    first = api.measurement(
        (random(), random(), random(), 0.7), (random() * 100, random() * 100)
    )
    positions = [(random() * 100, random() * 100) for _ in range(1, 5000)]
    color = (random(), random(), random(), 0.7)
    markers = api.measurement(color, positions)

    for i, m in enumerate(markers["markers"]):
        assert m["id"] == (1 + i) + first["id"]


def test_go_next():
    api = LSAPI()
    api.go_next()
