from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

from ndastro_mcp.http import create_app

_API_KEY = "test-only-api-key-not-a-real-secret-1234567890"
_HOST = "ndastro-example.onrender.com"
_HEADERS = {
    "Authorization": f"Bearer {_API_KEY}",
    "Accept": "application/json, text/event-stream",
}
_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"},
    },
}


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("NDASTRO_MCP_API_KEY", _API_KEY)
        patch.setenv("RENDER_EXTERNAL_HOSTNAME", _HOST)
        with TestClient(create_app(), base_url=f"https://{_HOST}") as http_client:
            yield http_client


@pytest.mark.parametrize("api_key", ["", "short", " " * 40, "x" * 32 + "\n", "x" * 32 + "\N{LATIN SMALL LETTER E WITH ACUTE}"])
def test_rejects_invalid_api_key(monkeypatch: pytest.MonkeyPatch, api_key: str):
    monkeypatch.setenv("NDASTRO_MCP_API_KEY", api_key)
    with pytest.raises(ValueError, match="NDASTRO_MCP_API_KEY"):
        create_app()


def test_rejects_missing_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("NDASTRO_MCP_API_KEY", raising=False)
    with pytest.raises(ValueError, match="NDASTRO_MCP_API_KEY"):
        create_app()


def test_public_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert client.head("/health").status_code == 200


@pytest.mark.parametrize("authorization", ["", "Bearer wrong", f"Basic {_API_KEY}", "Bearer"])
@pytest.mark.parametrize("method", ["GET", "POST", "DELETE"])
def test_rejects_unauthorized_requests(client: TestClient, method: str, authorization: str):
    response = client.request(method, "/mcp", headers={"Authorization": authorization})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == 'Bearer realm="ndastro"'
    assert _API_KEY not in response.text


@pytest.mark.parametrize("path", ["/mcp/", "/health/", "/sse", "/messages/"])
def test_other_paths_do_not_bypass_authentication(client: TestClient, path: str):
    assert client.post(path, json=_INITIALIZE).status_code == 401


def test_render_host_accepts_initialization(client: TestClient):
    response = client.post("/mcp", headers=_HEADERS, json=_INITIALIZE)
    assert response.status_code == 200
    assert response.json()["result"]["serverInfo"]["name"] == "ndastro"
    assert "mcp-session-id" not in response.headers


def test_bearer_scheme_is_case_insensitive(client: TestClient):
    headers = {**_HEADERS, "Authorization": f"bearer {_API_KEY}"}
    assert client.post("/mcp", headers=headers, json=_INITIALIZE).status_code == 200


def test_localhost_is_allowed(client: TestClient):
    headers = {**_HEADERS, "Host": "127.0.0.1:8000"}
    assert client.post("/mcp", headers=headers, json=_INITIALIZE).status_code == 200


def test_rejects_untrusted_host(client: TestClient):
    headers = {**_HEADERS, "Host": "untrusted.example"}
    assert client.post("/mcp", headers=headers, json=_INITIALIZE).status_code == 421


def test_rejects_untrusted_origin(client: TestClient):
    headers = {**_HEADERS, "Origin": "https://untrusted.example"}
    assert client.post("/mcp", headers=headers, json=_INITIALIZE).status_code == 403


def test_allows_render_origin(client: TestClient):
    headers = {**_HEADERS, "Origin": f"https://{_HOST}"}
    assert client.post("/mcp", headers=headers, json=_INITIALIZE).status_code == 200


def test_lists_real_tools_without_session_state(client: TestClient):
    response = client.post("/mcp", headers=_HEADERS, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert response.status_code == 200
    tools = {tool["name"] for tool in response.json()["result"]["tools"]}
    assert len(tools) == 16
    assert {"get_birth_chart", "get_current_dasa", "get_planet_positions"} <= tools


def test_calls_real_calculation_over_http(client: TestClient):
    response = client.post(
        "/mcp",
        headers=_HEADERS,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_ayanamsa_value",
                "arguments": {"datetime_iso": "2000-01-01T12:00:00Z", "system": "lahiri"},
            },
        },
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert not result["isError"]
    assert 23 < float(result["content"][0]["text"]) < 25
