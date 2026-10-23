"""Authenticated Streamable HTTP entry point for hosted deployments."""

import logging
import os
from secrets import compare_digest

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ndastro_mcp.server import mcp

logger = logging.getLogger(__name__)
_MIN_API_KEY_LENGTH = 32


class APIKeyMiddleware:
    """Require a bearer API key, except for the public health probe."""

    def __init__(self, app: ASGIApp, api_key: str) -> None:
        """Store the app and expected key without logging the secret."""
        self.app = app
        self.api_key = api_key.encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Reject unauthenticated requests before running MCP tools."""
        if scope["type"] != "http" or (scope["path"] == "/health" and scope["method"] in {"GET", "HEAD"}):
            await self.app(scope, receive, send)
            return

        authorization = Headers(scope=scope).get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not compare_digest(token.encode(), self.api_key):
            logger.warning("Rejected unauthenticated MCP request")
            response = JSONResponse(
                {"detail": "A valid bearer API key is required"},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="ndastro"'},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


async def health(_request: Request) -> JSONResponse:
    """Report readiness after the engine and MCP lifespan have started."""
    return JSONResponse({"status": "ok"})


def create_app() -> Starlette:
    """Create the private HTTP app; fail closed if the API key is missing."""
    api_key = os.environ.get("NDASTRO_MCP_API_KEY", "")
    if len(api_key) < _MIN_API_KEY_LENGTH or not api_key.isascii() or any(character.isspace() for character in api_key):
        msg = "NDASTRO_MCP_API_KEY must contain at least 32 ASCII characters without whitespace"
        raise ValueError(msg)

    allowed_hosts = ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*", "[::1]", "[::1]:*"]
    allowed_origins = ["http://localhost:*", "http://127.0.0.1:*", "http://[::1]:*"]
    render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if render_hostname:
        allowed_hosts.append(render_hostname)
        allowed_origins.append(f"https://{render_hostname}")

    mcp.settings.stateless_http = True
    mcp.settings.json_response = True
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )
    app = mcp.streamable_http_app()
    app.add_route("/health", health, methods=["GET"])
    app.add_middleware(APIKeyMiddleware, api_key=api_key)
    return app
