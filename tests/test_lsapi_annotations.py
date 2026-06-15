from laserstudio.lsapi import LSAPI
from random import random


def test_add_marker():
    api = LSAPI()
    m = api.marker(
        (random(), random(), random(), 0.7),
        p := (random() * 3000, random() * 3000),
        label="test",
    )
    assert list(p) == m["pos"]


def test_add_5000_markers_seq():
    api = LSAPI()
    first = api.marker(
        (random(), random(), random(), 0.7), (random() * 3000, random() * 3000)
    )
    col_pos = [
        ((random(), random(), random(), 0.7), (random() * 3000, random() * 3000))
        for _ in range(1, 5000)
    ]

    markers = [api.marker(color, pos) for (color, pos) in col_pos]

    for i, m in enumerate(markers):
        assert m["id"] == (1 + i) + first["id"]


def test_add_5000_markers_batch_by100():
    api = LSAPI()
    for _ in range(50):
        i = int(random() * 10)
        color = (random(), random(), random(), 0.7)
        first = api.marker(color, (random() * 3000, random() * 3000), label=f"Test {i}")
        positions = [(random() * 3000, random() * 3000) for _ in range(1, 100)]
        markers = api.marker(color, positions, label=f"Test {i}")

        for i, m in enumerate(markers["markers"]):
            assert m["id"] == (1 + i) + first["id"]


def test_add_5000_markers_in_one():
    api = LSAPI()
    color = (random(), random(), random(), 0.7)
    first = api.marker(color, (random() * 3000, random() * 3000))
    positions = [(random() * 3000, random() * 3000) for _ in range(1, 5000)]
    markers = api.marker(color, positions)

    for i, m in enumerate(markers["markers"]):
        assert m["id"] == (1 + i) + first["id"]


def test_get_markers() -> None:
    api = LSAPI()
    markers = api.markers()
    assert isinstance(markers, list)
    assert all(isinstance(marker, dict) for marker in markers)
    assert all("id" in marker for marker in markers)
    assert all("pos" in marker for marker in markers)
    assert all("color" in marker for marker in markers)


def test_delete_markers_by_id() -> None:
    api = LSAPI()
    m1 = api.marker((random(), random(), random(), 0.7), (random() * 3000, random()))
    m2 = api.marker((random(), random(), random(), 0.7), (random() * 3000, random()))

    result = api.delete_markers([m1["id"]])
    assert result["deleted"] == [m1["id"]]

    remaining_ids = [marker["id"] for marker in api.markers()]
    assert m1["id"] not in remaining_ids
    assert m2["id"] in remaining_ids


def test_delete_all_markers() -> None:
    api = LSAPI()
    api.marker((random(), random(), random(), 0.7), (random() * 3000, random()))
    api.marker((random(), random(), random(), 0.7), (random() * 3000, random()))

    result = api.delete_markers()
    assert isinstance(result["deleted"], list)
    assert api.markers() == []


def test_pixel_to_position() -> None:
    api = LSAPI()
    positions = api.pixel_to_position([(960, 540), (0, 0)])
    assert isinstance(positions, list)
    assert len(positions) == 2
    assert all(len(p) == 2 for p in positions)
    assert all(isinstance(v, (int, float)) for p in positions for v in p)


def test_pixel_to_position_single() -> None:
    api = LSAPI()
    positions = api.pixel_to_position((960, 540))
    assert len(positions) == 1
    assert len(positions[0]) == 2
