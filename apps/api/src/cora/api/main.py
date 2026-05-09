"""CORA FastAPI entrypoint.

Lifespan builds shared dependencies once at startup and exposes them on
`app.state.deps`. Each BC's `wire_*(deps)` function returns a handler
bundle stored on `app.state.<bc>`. Phase 1d wires Access handlers;
Phase 1e adds REST routers that pull handlers off `app.state.<bc>`;
Phase 1f adds MCP tools that do the same.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI

from cora import __version__
from cora.access.application import wire_access
from cora.access.infrastructure import register_access_routes
from cora.infrastructure.deps import build_shared_deps


def _is_valid_uuid(value: str) -> bool:
    """Validator for inbound X-Request-ID headers. UUID-only."""
    try:
        UUID(value)
    except ValueError:
        return False
    return True


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    deps, teardown = await build_shared_deps()
    app.state.deps = deps
    app.state.access = wire_access(deps)
    try:
        yield
    finally:
        await teardown()


app = FastAPI(
    title="CORA",
    version=__version__,
    description="Research facility operations platform",
    lifespan=lifespan,
)
app.add_middleware(
    CorrelationIdMiddleware,
    validator=_is_valid_uuid,
    generator=lambda: str(uuid4()),
)
register_access_routes(app)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "version": __version__}
