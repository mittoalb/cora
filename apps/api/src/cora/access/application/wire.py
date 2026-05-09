"""Compose the Access BC's handlers from `SharedDeps`.

`wire_access(deps)` is invoked once from the FastAPI lifespan and the
returned `AccessHandlers` bundle is stored on `app.state.access`.
Phase 1e routes and the Phase 1f MCP tool pull their handler out of
that bundle. New handlers (DeactivateActor, RenameActor, ...) become
new fields on `AccessHandlers` and a single line in this factory.
"""

from dataclasses import dataclass

from cora.access.application.register_actor import (
    RegisterActorHandler,
    make_register_actor_handler,
)
from cora.infrastructure.deps import SharedDeps


@dataclass(frozen=True)
class AccessHandlers:
    """The Access BC's handler bundle, each closed over SharedDeps."""

    register_actor: RegisterActorHandler


def wire_access(deps: SharedDeps) -> AccessHandlers:
    """Build the Access BC handlers from shared dependencies."""
    return AccessHandlers(
        register_actor=make_register_actor_handler(deps),
    )
