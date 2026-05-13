"""Compose the Access BC's handlers from `Kernel`.

`wire_access(deps)` is invoked once from the FastAPI lifespan and the
returned `AccessHandlers` bundle is stored on `app.state.access`. Routes
and MCP tools pull their handler out of that bundle. New slices
(commands or queries) add a new field on `AccessHandlers` and a single
line in this factory.

Cross-cutting decorators applied here (composition order matters —
innermost first):

1. `bind(deps)` — bare handler.
2. `with_idempotency` (create-style commands only) — Idempotency-Key
   support (`cora.infrastructure.idempotency`). Wrapped before tracing
   so cache-hits and cache-misses both attribute to the tracing span.
3. `with_tracing` — OTel span around every handler call. Records
   `cora.bc`, `cora.command` / `cora.query` attributes; on exception
   sets span status ERROR and records the exception.

Update-style commands (deactivate_actor) skip idempotency: they are
inherently idempotent at the domain level (second call hits
ActorAlreadyDeactivatedError). Queries (get_actor) skip idempotency:
no state mutation.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.access.features import (
    deactivate_actor,
    get_actor,
    list_actors,
    register_actor,
)
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing

_BC = "access"


@dataclass(frozen=True)
class AccessHandlers:
    """The Access BC's handler bundle, each closed over Kernel.

    Field types reflect what's stored: register_actor is the
    idempotency-wrapped variant (signature gains optional
    idempotency_key kwarg); deactivate_actor and get_actor remain
    bare handlers (no idempotency in Phase 2d). All three are
    additionally wrapped with `with_tracing`, which preserves the
    underlying call signature.
    """

    register_actor: register_actor.IdempotentHandler
    deactivate_actor: deactivate_actor.Handler
    get_actor: get_actor.Handler
    list_actors: list_actors.Handler


def wire_access(deps: Kernel) -> AccessHandlers:
    """Build the Access BC handlers from shared dependencies."""
    return AccessHandlers(
        register_actor=with_tracing(
            with_idempotency(
                register_actor.bind(deps),
                deps.idempotency_store,
                command_name="RegisterActor",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterActor",
            bc=_BC,
        ),
        deactivate_actor=with_tracing(
            deactivate_actor.bind(deps),
            command_name="DeactivateActor",
            bc=_BC,
        ),
        get_actor=with_tracing(
            get_actor.bind(deps),
            command_name="GetActor",
            bc=_BC,
            kind="query",
        ),
        list_actors=with_tracing(
            list_actors.bind(deps),
            command_name="ListActors",
            bc=_BC,
            kind="query",
        ),
    )
