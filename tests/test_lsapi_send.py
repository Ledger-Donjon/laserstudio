"""Offline unit tests for ``LSAPI.send``'s HTTP verb dispatch.

Unlike ``tests/test_lsapi_*.py`` (which need a live Laser Studio listening on
port 4444), this module is a pure unit test: ``LSAPI.session`` is replaced
with an in-process stub that just records ``(verb, url, json)`` and returns a
canned response, so nothing here ever touches the network.

It covers the verb-selection rules of ``send()``:

- Each of GET/POST/PUT/PATCH/DELETE is produced for the appropriate flag
  combination.
- An explicitly requested verb (``is_put``/``is_patch``) wins over the
  ``params is None`` -> GET fallback, so a PUT/PATCH with no payload is still
  sent as PUT/PATCH (with an empty body) rather than silently becoming a GET.
- Passing more than one of ``is_put``/``is_patch``/``is_delete`` raises
  ``ValueError``.
- A handful of real client methods (``go_to``, ``set_scangeometry``,
  ``update_scan_zone``, ``delete_scan_zone``) produce the verb and URL their
  corresponding server route actually accepts.
"""

from __future__ import annotations

from typing import Any

import pytest

from laserstudio.lsapi import LSAPI


class _FakeResponse:
    """Minimal stand-in for ``requests.Response``."""

    status_code = 200
    ok = True

    def json(self) -> dict[str, Any]:
        return {}

    def raise_for_status(self) -> None:
        pass


class _FakeSession:
    """Records every HTTP call made through it as ``(verb, url, json)``."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any]] = []

    def _record(self, verb: str):
        def _call(url: str, json: Any = None) -> _FakeResponse:
            self.calls.append((verb, url, json))
            return _FakeResponse()

        return _call

    def __getattr__(self, name: str):
        return self._record(name.upper())

    def close(self) -> None:
        pass


@pytest.fixture()
def api() -> LSAPI:
    instance = LSAPI()
    instance.session = _FakeSession()  # type: ignore[assignment]
    return instance


def _last_call(instance: LSAPI) -> tuple[str, str, Any]:
    session = instance.session
    assert isinstance(session, _FakeSession)
    return session.calls[-1]


class TestVerbSelection:
    def test_no_params_is_get(self, api: LSAPI) -> None:
        api.send("thing")
        verb, url, json = _last_call(api)
        assert verb == "GET"
        assert url.endswith("/thing")
        assert json is None

    def test_params_with_no_flags_is_post(self, api: LSAPI) -> None:
        api.send("thing", {"a": 1})
        verb, _, json = _last_call(api)
        assert verb == "POST"
        assert json == {"a": 1}

    def test_is_put_with_params(self, api: LSAPI) -> None:
        api.send("thing", {"a": 1}, is_put=True)
        verb, _, json = _last_call(api)
        assert verb == "PUT"
        assert json == {"a": 1}

    def test_is_patch_with_params(self, api: LSAPI) -> None:
        api.send("thing", {"a": 1}, is_patch=True)
        verb, _, json = _last_call(api)
        assert verb == "PATCH"
        assert json == {"a": 1}

    def test_is_delete(self, api: LSAPI) -> None:
        api.send("thing", is_delete=True)
        verb, _, json = _last_call(api)
        assert verb == "DELETE"
        assert json is None

    def test_is_put_with_no_params_stays_put(self, api: LSAPI) -> None:
        """An explicit PUT must not be downgraded to a GET just because
        there is no payload -- this is exactly the bug ``go_to`` used to
        trigger against a real server (see ``test_go_to_is_a_put_not_a_get``
        below)."""
        api.send("thing", is_put=True)
        verb, _, json = _last_call(api)
        assert verb == "PUT"
        assert json is None

    def test_is_patch_with_no_params_stays_patch(self, api: LSAPI) -> None:
        api.send("thing", is_patch=True)
        verb, _, json = _last_call(api)
        assert verb == "PATCH"
        assert json is None

    def test_is_delete_with_no_params(self, api: LSAPI) -> None:
        api.send("thing", is_delete=True)
        verb, _, json = _last_call(api)
        assert verb == "DELETE"
        assert json is None

    @pytest.mark.parametrize(
        "flags",
        [
            {"is_put": True, "is_patch": True},
            {"is_put": True, "is_delete": True},
            {"is_patch": True, "is_delete": True},
            {"is_put": True, "is_patch": True, "is_delete": True},
        ],
    )
    def test_contradictory_flags_raise(
        self, api: LSAPI, flags: dict[str, bool]
    ) -> None:
        with pytest.raises(ValueError):
            api.send("thing", **flags)


class TestRealCallSites:
    """A handful of real ``LSAPI`` methods, checked against the verb and URL
    their corresponding server route (``laserstudio/restserver/server.py``)
    actually accepts."""

    def test_go_to_is_a_put_not_a_get(self, api: LSAPI) -> None:
        api.go_to(3)
        verb, url, json = _last_call(api)
        assert verb == "PUT"
        assert url.endswith("/motion/go_to_memory_point/3")
        assert json is None

    def test_set_scangeometry_is_a_put(self, api: LSAPI) -> None:
        api.set_scangeometry({"zones": []})
        verb, url, json = _last_call(api)
        assert verb == "PUT"
        assert url.endswith("/scangeometry")
        assert json == {"settings": {"zones": []}}

    def test_update_scan_zone_is_a_patch(self, api: LSAPI) -> None:
        api.update_scan_zone(2, enabled=False)
        verb, url, json = _last_call(api)
        assert verb == "PATCH"
        assert url.endswith("/scangeometry/zones/2")
        assert json == {
            "name": None,
            "color": None,
            "enabled": False,
            "geometry": None,
        }

    def test_delete_scan_zone_is_a_delete(self, api: LSAPI) -> None:
        api.delete_scan_zone(2)
        verb, url, json = _last_call(api)
        assert verb == "DELETE"
        assert url.endswith("/scangeometry/zones/2")
        assert json is None

    def test_instrument_settings_getter_is_still_a_get(self, api: LSAPI) -> None:
        """``instrument_settings(label)`` with no settings must remain a GET
        (its route has no body and requires none): the new dispatch order
        makes an explicit ``is_put`` win over the params-is-None fallback, so
        this call site now passes ``is_put`` conditionally to avoid turning
        into a body-required PUT."""
        api.instrument_settings("lbl")
        verb, url, json = _last_call(api)
        assert verb == "GET"
        assert url.endswith("/instruments/lbl/settings")
        assert json is None

    def test_instrument_settings_setter_is_a_put(self, api: LSAPI) -> None:
        api.instrument_settings("lbl", {"x": 1})
        verb, _, json = _last_call(api)
        assert verb == "PUT"
        assert json == {"x": 1}
