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

Observability stack:
- OpenTelemetry tracing is configured at app construction; the global
  TracerProvider is installed iff `settings.otel_exporter != "none"`.
  Per-app FastAPI instrumentation is attached after app creation.
  The W3C `traceparent` header is the source of truth for "this
  request" identity; the prior `asgi-correlation-id` middleware was
  removed because OTel's TraceContextTextMapPropagator handles inbound
  / outbound trace propagation per the W3C spec.
- Prometheus metrics are exposed on `/metrics` (operational endpoint,
  excluded from OpenAPI schema).
- structlog is configured in `build_shared_deps()`; an OTel processor
  injects `trace_id` and `span_id` into every log line emitted inside
  an active span.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

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
from cora.equipment import (
    EquipmentHandlers,
    register_equipment_routes,
    register_equipment_tools,
    wire_equipment,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import build_shared_deps
from cora.infrastructure.observability import configure_tracing, instrument_app
from cora.recipe import (
    RecipeHandlers,
    register_recipe_routes,
    register_recipe_tools,
    wire_recipe,
)
from cora.subject import (
    SubjectHandlers,
    register_subject_routes,
    register_subject_tools,
    wire_subject,
)
from cora.trust import (
    TrustHandlers,
    register_trust_routes,
    register_trust_tools,
    wire_trust,
)


def _settings_for_app() -> Settings:
    """Load Settings at app construction for one-shot wiring decisions.

    The lifespan also constructs Settings; both calls hit env vars / .env
    so they agree. Pulled into a helper purely for readability.
    """
    return Settings()  # type: ignore[call-arg]  # Pydantic loads from env


def create_app() -> FastAPI:
    """Build a fresh FastAPI app with its own FastMCP server instance.

    Production calls this once at module import; tests call it per
    `TestClient` context to get isolation.
    """
    settings = _settings_for_app()
    # configure_tracing is a no-op when otel_exporter == "none" (the
    # default in tests), so calling it per create_app() is safe. In
    # production it runs once and installs the global TracerProvider.
    tracing_teardown = configure_tracing(settings)

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

    def _get_trust_handlers() -> TrustHandlers:
        handlers: TrustHandlers = fastapi_app.state.trust
        return handlers

    def _get_subject_handlers() -> SubjectHandlers:
        handlers: SubjectHandlers = fastapi_app.state.subject
        return handlers

    def _get_equipment_handlers() -> EquipmentHandlers:
        handlers: EquipmentHandlers = fastapi_app.state.equipment
        return handlers

    def _get_recipe_handlers() -> RecipeHandlers:
        handlers: RecipeHandlers = fastapi_app.state.recipe
        return handlers

    register_access_tools(mcp, get_handlers=_get_access_handlers)
    register_trust_tools(mcp, get_handlers=_get_trust_handlers)
    register_subject_tools(mcp, get_handlers=_get_subject_handlers)
    register_equipment_tools(mcp, get_handlers=_get_equipment_handlers)
    register_recipe_tools(mcp, get_handlers=_get_recipe_handlers)
    mcp_app = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        # MCP session manager first (per python-sdk#1367), then our
        # shared deps inside it so both surfaces share one wiring.
        async with mcp_app.router.lifespan_context(app):
            deps, teardown = await build_shared_deps()
            app.state.deps = deps
            app.state.access = wire_access(deps)
            app.state.trust = wire_trust(deps)
            app.state.subject = wire_subject(deps)
            app.state.equipment = wire_equipment(deps)
            app.state.recipe = wire_recipe(deps)
            try:
                yield
            finally:
                # Independent try/finally for each teardown so an
                # exception in the asyncpg pool close (rare but
                # observed under DB-side connection drops at shutdown)
                # doesn't skip the tracing flush. Without this, any
                # spans buffered by BatchSpanProcessor would be lost.
                try:
                    await teardown()
                finally:
                    # Flush pending OTel spans before the process exits
                    # so short-lived runs (CLI invocations, smoke tests)
                    # don't drop traces. No-op when tracing is off.
                    tracing_teardown()

    fastapi_app = FastAPI(
        title="CORA",
        version=__version__,
        description="Research facility operations platform",
        lifespan=lifespan,
    )
    fastapi_app.add_middleware(
        BodySizeLimitMiddleware,
        max_bytes=settings.max_request_body_size_bytes,
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
    # OTel FastAPI instrumentation runs after app construction so the
    # FastAPIInstrumentor sees every route registered above plus the
    # ones registered below. No-op when tracing is off.
    instrument_app(fastapi_app, settings)
    register_access_routes(fastapi_app)
    register_trust_routes(fastapi_app)
    register_subject_routes(fastapi_app)
    register_equipment_routes(fastapi_app)
    register_recipe_routes(fastapi_app)
    fastapi_app.mount("/mcp", mcp_app)

    @fastapi_app.get("/health")
    async def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """Liveness probe."""
        return {"status": "ok", "version": __version__}

    return fastapi_app


app = create_app()
