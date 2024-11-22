from laserstudio.lsapi import LSAPI
from random import random


def test_add_marker():
    api = LSAPI()
    m = api.marker(
        (random(), random(), random(), 0.7), p := (random() * 100, random() * 100)
    )
    assert list(p) == m["pos"]


def test_add_5000_markers_seq():
    api = LSAPI()
    first = api.marker(
        (random(), random(), random(), 0.7), (random() * 100, random() * 100)
    )
    col_pos = [
        ((random(), random(), random(), 0.7), (random() * 100, random() * 100))
        for _ in range(1, 5000)
    ]

    markers = [api.marker(color, pos) for (color, pos) in col_pos]

    for i, m in enumerate(markers):
        assert m["id"] == (1 + i) + first["id"]


def test_add_5000_markers_batch_by100():
    api = LSAPI()
    for _ in range(50):
        color = (random(), random(), random(), 0.7)
        first = api.marker(
            color, (random() * 100, random() * 100)
        )
        positions = [(random() * 100, random() * 100) for _ in range(1, 100)]
        markers = api.marker(color, positions)

        for i, m in enumerate(markers["markers"]):
            assert m["id"] == (1 + i) + first["id"]


def test_add_5000_markers_in_one():
    api = LSAPI()
    color = (random(), random(), random(), 0.7)
    first = api.marker(
        color, (random() * 100, random() * 100)
    )
    positions = [(random() * 100, random() * 100) for _ in range(1, 5000)]
    markers = api.marker(color, positions)

    for i, m in enumerate(markers["markers"]):
        assert m["id"] == (1 + i) + first["id"]


def test_go_next():
    api = LSAPI()
    api.go_next()
