import asyncio
from typing import Any

import httpx
import pytest

from ndastro_mcp import api, api_tools, server

_BIRTH = "1985-07-31T04:25:00+05:30"


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, method: str, path: str, **kwargs: object) -> dict[str, Any]:
        self.calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    calls = _Recorder()
    monkeypatch.setattr(api, "request", calls)
    return calls


def test_glossary_tool_returns_api_payload_through_mcp(monkeypatch: pytest.MonkeyPatch):
    payload = {"language": "ta", "planets": {"SA": "சனி"}, "rasis": {}, "nakshatras": {}, "dasa_levels": {}}
    monkeypatch.setattr(api, "glossary", lambda _language: payload)

    _, structured = asyncio.run(server.mcp.call_tool("get_glossary", {"language": "ta"}))

    assert structured["language"] == "ta"
    assert structured["planets"]["SA"] == "சனி"


def test_event_timing_maps_parameters(recorder: _Recorder):
    api_tools.get_event_timing(_BIRTH, 11.85, 77.75, "marriage", gender="male", language="ta")

    call = recorder.calls[0]
    assert (call["method"], call["path"]) == ("GET", "/life-timeline/event-timing")
    assert call["params"]["event"] == "marriage"
    assert call["params"]["gender"] == "male"
    assert call["params"]["lang"] == "ta"


def test_calibration_posts_known_events(recorder: _Recorder):
    events = [api_tools.KnownEvent(event="land_purchase", actual_event_datetime="2018-10-11T02:20:00+05:30")]
    api_tools.calibrate_with_known_events(_BIRTH, 11.85, 77.75, events)

    call = recorder.calls[0]
    assert (call["method"], call["path"]) == ("POST", "/life-timeline/calibrate")
    assert call["json"]["events"] == [{"event": "land_purchase", "actual_event_datetime": "2018-10-11T02:20:00+05:30"}]


def test_birth_time_correction_searches_both_directions(recorder: _Recorder):
    events = [api_tools.KnownEvent(event="marriage", actual_event_datetime="2013-06-12T05:15:00+05:30")]
    api_tools.correct_birth_datetime(_BIRTH, 11.85, 77.75, events, search_minutes=30)

    body = recorder.calls[0]["json"]
    assert body["search_minutes_before"] == body["search_minutes_after"] == 30


def _respond(monkeypatch: pytest.MonkeyPatch, response: httpx.Response | Exception) -> list[dict[str, Any]]:
    seen: list[dict[str, Any]] = []

    def fake_request(method: str, url: str, **kwargs: object) -> httpx.Response:
        seen.append({"method": method, "url": url, **kwargs})
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(api.httpx, "request", fake_request)
    return seen


def test_request_drops_unset_parameters(monkeypatch: pytest.MonkeyPatch):
    seen = _respond(monkeypatch, httpx.Response(200, json={"ok": True}))

    assert api.request("GET", "/glossary", params={"lang": "ta", "gender": None}) == {"ok": True}
    assert seen[0]["params"] == {"lang": "ta"}
    assert seen[0]["url"].endswith("/glossary")


def test_request_reports_unreachable_api(monkeypatch: pytest.MonkeyPatch):
    _respond(monkeypatch, httpx.ConnectError("refused"))

    with pytest.raises(api.ApiError, match="not reachable"):
        api.request("GET", "/glossary")


def test_request_surfaces_api_error_detail(monkeypatch: pytest.MonkeyPatch):
    _respond(monkeypatch, httpx.Response(422, json={"detail": "Unsupported events: x"}))

    with pytest.raises(api.ApiError, match="Unsupported events"):
        api.request("GET", "/life-timeline/event-timing")
