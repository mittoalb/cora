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
from prometheus_client import CollectorRegistry
from prometheus_fastapi_instrumentator import Instrumentator

from cora import __version__
from cora.access import (
    AccessHandlers,
    register_access_routes,
    register_access_tools,
    wire_access,
)
from cora.api.middleware import BodySizeLimitMiddleware
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import build_shared_deps


def _is_valid_uuid(value: str) -> bool:
    """Validator for inbound X-Request-ID headers. UUID-only."""
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def _settings_for_middleware() -> Settings:
    """Load Settings at app construction for middleware that needs config.

    The lifespan also constructs Settings; both calls hit env vars / .env
    so they agree. Pulled into a helper purely for readability.
    """
    return Settings()  # type: ignore[call-arg]  # Pydantic loads from env


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
    # Middleware add order is reversed at request time: the LAST one
    # added runs FIRST on incoming requests. We want correlation_id set
    # outermost so the 413 from BodySizeLimit also carries it on the
    # response, so add body-limit first then correlation last.
    fastapi_app.add_middleware(
        BodySizeLimitMiddleware,
        max_bytes=_settings_for_middleware().max_request_body_size_bytes,
    )
    fastapi_app.add_middleware(
        CorrelationIdMiddleware,
        validator=_is_valid_uuid,
        generator=lambda: str(uuid4()),
    )
    # Prometheus instrumentation:
    # - per-app CollectorRegistry so multiple create_app() calls in the
    #   test process don't double-register collectors against the global
    #   REGISTRY (which would crash the second TestClient).
    # - excluded_handlers=["/metrics"] keeps the scrape endpoint out of
    #   its own counters (otherwise each scrape pollutes its own metrics
    #   with monitoring traffic).
    # - include_in_schema=False hides /metrics from OpenAPI /docs (it's
    #   an operational endpoint, not part of the user-facing API).
    metrics_registry = CollectorRegistry()
    Instrumentator(
        registry=metrics_registry,
        excluded_handlers=["/metrics"],
    ).instrument(fastapi_app).expose(fastapi_app, include_in_schema=False)
    register_access_routes(fastapi_app)
    fastapi_app.mount("/mcp", mcp_app)

    @fastapi_app.get("/health")
    async def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """Liveness probe."""
        return {"status": "ok", "version": __version__}

    return fastapi_app


app = create_app()
