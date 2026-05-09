"""Compose the Access BC's handlers from `SharedDeps`.

`wire_access(deps)` is invoked once from the FastAPI lifespan and the
returned `AccessHandlers` bundle is stored on `app.state.access`. Routes
and MCP tools pull their handler out of that bundle. New slices add a
new field on `AccessHandlers` and a single line in this factory.
"""

from dataclasses import dataclass

from cora.access.features import deactivate_actor, register_actor
from cora.infrastructure.deps import SharedDeps


@dataclass(frozen=True)
class AccessHandlers:
    """The Access BC's handler bundle, each closed over SharedDeps."""

    register_actor: register_actor.Handler
    deactivate_actor: deactivate_actor.Handler


def wire_access(deps: SharedDeps) -> AccessHandlers:
    """Build the Access BC handlers from shared dependencies."""
    return AccessHandlers(
        register_actor=register_actor.bind(deps),
        deactivate_actor=deactivate_actor.bind(deps),
    )
