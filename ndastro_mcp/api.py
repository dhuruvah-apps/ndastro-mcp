"""HTTP client for ndastro-api."""

import os
from functools import lru_cache
from typing import Any, Literal

import httpx

Language = Literal["en", "hi", "ta", "te", "kn", "ml"]
LANGUAGES: tuple[Language, ...] = ("en", "hi", "ta", "te", "kn", "ml")

API_URL = os.environ.get("NDASTRO_API_URL", "http://localhost:6001/api/v1").rstrip("/")
_TOKEN = os.environ.get("NDASTRO_API_TOKEN")
_DEFAULT_TIMEOUT = 120.0


class ApiError(RuntimeError):
    """ndastro-api could not be reached or rejected the request."""


def request(
    method: Literal["GET", "POST"],
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: Any = None,  # noqa: ANN401
    timeout: float = _DEFAULT_TIMEOUT,
) -> Any:  # noqa: ANN401
    """Call ndastro-api and return the decoded JSON body."""
    headers = {"Authorization": f"Bearer {_TOKEN}"} if _TOKEN else {}
    clean_params = {key: value for key, value in (params or {}).items() if value is not None}
    try:
        response = httpx.request(method, f"{API_URL}{path}", params=clean_params, json=json, headers=headers, timeout=timeout)
    except httpx.TransportError as exc:
        msg = f"ndastro-api is not reachable at {API_URL} ({exc}). Start it or set NDASTRO_API_URL."
        raise ApiError(msg) from exc
    if response.is_error:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        msg = f"ndastro-api returned {response.status_code} for {path}: {detail}"
        raise ApiError(msg)
    return response.json()


@lru_cache(maxsize=len(LANGUAGES))
def glossary(language: Language) -> dict[str, Any]:
    """Return the language plus localized planet, rasi, nakshatra, and dasa level names keyed by code."""
    return request("GET", "/glossary", params={"lang": language})
