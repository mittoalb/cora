"""Compose the Access BC's handlers from `SharedDeps`.

`wire_access(deps)` is invoked once from the FastAPI lifespan and the
returned `AccessHandlers` bundle is stored on `app.state.access`. Routes
and MCP tools pull their handler out of that bundle. New slices
(commands or queries) add a new field on `AccessHandlers` and a single
line in this factory.

Cross-cutting decorators applied here (Phase 2d):
- `with_idempotency`: wraps create-style command handlers with
  Idempotency-Key support (`cora.access._idempotency`). Update-style
  commands (deactivate_actor) are inherently idempotent at the domain
  level (second call hits ActorAlreadyDeactivatedError); applying the
  decorator there is a future enhancement when concurrent-retry-then-
  cached-response semantics are needed.
- Queries (get_actor) don't need idempotency (no state mutation).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.access._idempotency import with_idempotency
from cora.access.features import deactivate_actor, get_actor, register_actor
from cora.infrastructure.deps import SharedDeps


@dataclass(frozen=True)
class AccessHandlers:
    """The Access BC's handler bundle, each closed over SharedDeps.

    Field types reflect what's stored: register_actor is the
    idempotency-wrapped variant (signature gains optional
    idempotency_key kwarg); deactivate_actor and get_actor remain
    bare handlers (no idempotency in Phase 2d).
    """

    register_actor: register_actor.IdempotentHandler
    deactivate_actor: deactivate_actor.Handler
    get_actor: get_actor.Handler


def wire_access(deps: SharedDeps) -> AccessHandlers:
    """Build the Access BC handlers from shared dependencies."""
    return AccessHandlers(
        register_actor=with_idempotency(
            register_actor.bind(deps),
            deps.idempotency_store,
            command_name="RegisterActor",
            # Handler returns UUID; cache as str (jsonb-friendly) and
            # rebuild via UUID() on retrieval.
            serialize_result=str,
            deserialize_result=UUID,
        ),
        deactivate_actor=deactivate_actor.bind(deps),
        get_actor=get_actor.bind(deps),
    )
