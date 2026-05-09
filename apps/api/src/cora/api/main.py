"""CORA FastAPI entrypoint.

`create_app()` is the factory: each call builds a fresh FastMCP server,
fresh FastAPI app, fresh middleware stack. The module-level `app` is
the production singleton (uvicorn imports it). Tests call `create_app()`
to get isolated instances — necessary because FastMCP's
StreamableHTTPSessionManager raises if the same instance's `.run()` is
called twice (once per lifespan), so reusing the module-level app
across multiple TestClient context managers fails.

Lifespan composition: the MCP session manager's lifespan must wrap our
shared-deps build so the manager initializes before any MCP request.
Without the wrap, mounted MCP requests silently fail
(modelcontextprotocol/python-sdk#1367).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from cora import __version__
from cora.access import (
    AccessHandlers,
    register_access_routes,
    register_access_tools,
    wire_access,
)
from cora.infrastructure.deps import build_shared_deps


def _is_valid_uuid(value: str) -> bool:
    """Validator for inbound X-Request-ID headers. UUID-only."""
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def create_app() -> FastAPI:
    """Build a fresh FastAPI app with its own FastMCP server instance.

    Production calls this once at module import; tests call it per
    `TestClient` context to get isolation.
    """
    # streamable_http_path="/" makes the inner MCP route the mount root,
    # so the full path under app.mount("/mcp", ...) is just "/mcp"
    # (otherwise the default "/mcp" inner path produces "/mcp/mcp").
    # transport_security: FastMCP's DNS-rebinding protection rejects
    # unknown Host headers. We're embedded in FastAPI behind the host
    # security FastAPI / the deployment proxy already enforces, so we
    # relax MCP's check here.
    mcp = FastMCP(
        "cora",
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )

    fastapi_app: FastAPI

    def _get_access_handlers() -> AccessHandlers:
        handlers: AccessHandlers = fastapi_app.state.access
        return handlers

    register_access_tools(mcp, get_handlers=_get_access_handlers)
    mcp_app = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        # MCP session manager first (per python-sdk#1367), then our
        # shared deps inside it so both surfaces share one wiring.
        async with mcp_app.router.lifespan_context(app):
            deps, teardown = await build_shared_deps()
            app.state.deps = deps
            app.state.access = wire_access(deps)
            try:
                yield
            finally:
                await teardown()

    fastapi_app = FastAPI(
        title="CORA",
        version=__version__,
        description="Research facility operations platform",
        lifespan=lifespan,
    )
    fastapi_app.add_middleware(
        CorrelationIdMiddleware,
        validator=_is_valid_uuid,
        generator=lambda: str(uuid4()),
    )
    register_access_routes(fastapi_app)
    fastapi_app.mount("/mcp", mcp_app)

    @fastapi_app.get("/health")
    async def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """Liveness probe."""
        return {"status": "ok", "version": __version__}

    return fastapi_app


app = create_app()
