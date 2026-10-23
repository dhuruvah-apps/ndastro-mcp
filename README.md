# ndastro MCP server

MCP tools for Vedic astrology calculations powered by `ndastro-engine`.
The same tools are available locally over stdio or remotely over Streamable HTTP.

## Local desktop use

Install Python 3.13.1 and Poetry, then run these commands from the repository:

```powershell
poetry install
poetry run ndastro-mcp
```

The existing [`.mcp.json`](.mcp.json) starts the stdio server for local MCP clients.
The local stdio workflow does not require an API key.

## Deploy to Render

1. Push this repository, including [`render.yaml`](render.yaml) and `poetry.lock`,
   to GitHub.
2. In the [Render dashboard](https://dashboard.render.com/), choose **New > Blueprint**
   and connect that repository.
3. Review the Blueprint and deploy. It selects a **paid Starter web service** to
   avoid free-service idle spin-down. Review current Render pricing before approving.
4. Render generates a secret `NDASTRO_MCP_API_KEY`. Copy its value from the
   service's **Environment** settings into your MCP client's bearer header.
   Treat this value as a password; never commit it.
5. Check `https://YOUR-SERVICE.onrender.com/health`. A ready service returns
   `{"status":"ok"}`. The MCP endpoint is
   `https://YOUR-SERVICE.onrender.com/mcp`.

The Blueprint binds Uvicorn to `0.0.0.0` and Render's `$PORT`. It pins Python
below the engine's unsupported 3.14 ceiling and installs production dependencies
from the Poetry lockfile. The build imports the engine to download its ephemeris
data into `.render-data` before startup; the initial build needs internet access
and can take longer while this data downloads. The data is included in the build,
so a persistent disk is not required.

The HTTP entry point refuses to start without an API key containing at least
32 ASCII characters without whitespace. All HTTP paths except `GET`/`HEAD`
`/health` require the bearer key. The health response contains no chart or user
data. MCP host/origin validation stays enabled and permits Render's automatically
provided `RENDER_EXTERNAL_HOSTNAME`, plus localhost for development.
Use the Render hostname; custom domains and browser-based CORS clients are not
configured by this Blueprint.

### Manual Render web service setup

If you prefer not to use a Blueprint, select the Python runtime and use:

| Setting | Value |
| --- | --- |
| Build command | `poetry install --only main && poetry run python -c "import ndastro_mcp.server"` |
| Start command | `poetry run uvicorn ndastro_mcp.http:create_app --factory --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |
| `PYTHON_VERSION` | `3.13.1` |
| `POETRY_VERSION` | `2.4.1` |
| `XDG_DATA_HOME` | `.render-data` |
| `NDASTRO_MCP_API_KEY` | A randomly generated secret of at least 32 characters |

For a monorepo, set Render's **Root Directory** to the directory containing this
project's `pyproject.toml`.

## Connect the GitHub Copilot desktop app

In **Customize > MCP**, add a custom HTTP server using the `/mcp` URL and
an `Authorization` header with the value `Bearer YOUR_API_KEY`.
Alternatively, merge this entry into the `mcpServers` object in
`%USERPROFILE%\.copilot\mcp-config.json`:

```json
{
  "mcpServers": {
    "ndastro": {
      "type": "http",
      "url": "https://YOUR-SERVICE.onrender.com/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      },
      "tools": ["*"]
    }
  }
}
```

Replace an existing local `ndastro` entry rather than adding a duplicate. Reload
the client and ask: "Use ndastro to list the supported ayanamsa systems."

This uses a shared static bearer key, not an OAuth login flow. Only clients that
support configuring authorization headers can connect. Anyone holding the key
can use all tools; this is not per-user authorization or rate limiting. Long
retrograde/combustion scans can be CPU-intensive, so share the key only with
trusted users and monitor Render resource usage.

## Run the hosted entry point locally

```powershell
$env:NDASTRO_MCP_API_KEY = "<random-secret-at-least-32-characters>"
poetry run uvicorn ndastro_mcp.http:create_app --factory --host 127.0.0.1 --port 8000
```

Use `http://127.0.0.1:8000/mcp` in your client. `/health` is a normal HTTP
endpoint, but `/mcp` speaks the MCP protocol and is not a browser UI.
The older `ndastro-mcp --transport streamable-http` and `--transport sse`
commands do not install the private hosted wrapper; do not use them as the
Render start command.

## Tests

```powershell
poetry install
poetry run pytest
poetry run ruff check .
```
