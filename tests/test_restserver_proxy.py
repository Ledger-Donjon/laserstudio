from types import SimpleNamespace
from typing import Any

from laserstudio.restserver.server import RestProxy


class RulerHandlers:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def handle_rulers(self) -> list[dict[str, int]]:
        self.calls.append(("handle_rulers", ()))
        return [{"id": 1}]

    def handle_add_rulers(
        self,
        segments: list[list[float]] | None,
        color: list[float] | None,
        label: str | None,
        graduation: float | None,
        graduation_count: float | None,
        visible: bool | None,
    ) -> dict[str, int]:
        self.calls.append(
            (
                "handle_add_rulers",
                (segments, color, label, graduation, graduation_count, visible),
            )
        )
        return {"id": 2}

    def handle_delete_rulers(self, ids: list[int] | None) -> dict[str, list[int]]:
        self.calls.append(("handle_delete_rulers", (ids,)))
        return {"deleted": ids or []}


def test_rest_proxy_delegates_get_rulers() -> None:
    laser_studio = RulerHandlers()
    proxy = SimpleNamespace(laser_studio=laser_studio)

    result = RestProxy.handle_rulers(proxy)

    assert result == [{"id": 1}]
    assert laser_studio.calls == [("handle_rulers", ())]


def test_rest_proxy_delegates_add_rulers() -> None:
    laser_studio = RulerHandlers()
    proxy = SimpleNamespace(laser_studio=laser_studio)
    segments = [[1.0, 2.0, 3.0, 4.0]]
    color = [1.0, 0.5, 0.0, 1.0]

    result = RestProxy.handle_add_rulers(
        proxy, segments, color, "scale", 10.0, None, False
    )

    assert result == {"id": 2}
    assert laser_studio.calls == [
        ("handle_add_rulers", (segments, color, "scale", 10.0, None, False))
    ]


def test_rest_proxy_delegates_delete_rulers() -> None:
    laser_studio = RulerHandlers()
    proxy = SimpleNamespace(laser_studio=laser_studio)

    result = RestProxy.handle_delete_rulers(proxy, [2, 3])

    assert result == {"deleted": [2, 3]}
    assert laser_studio.calls == [("handle_delete_rulers", ([2, 3],))]
