"""Shared application dependencies — built once at startup, passed to BC modules.

Each BC's `wire_*(deps)` function pulls the ports it needs from `SharedDeps`
to build its handlers, routes, and MCP tools.

Phase 1a wires Settings + logging + Clock + IdGenerator + a stub Authorize.
Phase 1b adds EventStore + EventPublisher (real Postgres adapters). Phase 3
swaps `AllowAllAuthorize` for the Trust-backed adapter.
"""

from dataclasses import dataclass

from cora.infrastructure.config import Settings
from cora.infrastructure.logging import configure_logging
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    Authorize,
    Clock,
    IdGenerator,
    SystemClock,
    UUIDv7Generator,
)


@dataclass(frozen=True)
class SharedDeps:
    """Process-wide dependencies. Immutable after `build_shared_deps` returns."""

    settings: Settings
    clock: Clock
    id_generator: IdGenerator
    authorize: Authorize


async def build_shared_deps() -> SharedDeps:
    """Construct shared dependencies. Called once from the FastAPI lifespan."""
    settings = Settings()  # type: ignore[call-arg]  # Pydantic loads from env
    configure_logging(settings.log_level)
    return SharedDeps(
        settings=settings,
        clock=SystemClock(),
        id_generator=UUIDv7Generator(),
        authorize=AllowAllAuthorize(),
    )


async def teardown_shared_deps(deps: SharedDeps) -> None:
    """Release any resources held by shared dependencies. Phase 1a is a no-op."""
    _ = deps  # keep signature stable; later phases will close DB pools etc.
