"""CORA FastAPI entrypoint.

Lifespan builds shared dependencies once at startup and exposes them on
`app.state.deps`. Each BC's `wire_*(deps)` function (added Phase 1c onward)
contributes its router and MCP tools.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI

from cora import __version__
from cora.infrastructure.deps import build_shared_deps


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    deps, teardown = await build_shared_deps()
    app.state.deps = deps
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
app.add_middleware(CorrelationIdMiddleware)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "version": __version__}
