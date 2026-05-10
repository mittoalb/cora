"""Compose the Trust BC's handlers from `SharedDeps`.

`wire_trust(deps)` is invoked once from the FastAPI lifespan and the
returned `TrustHandlers` bundle is stored on `app.state.trust`. Routes
and MCP tools pull their handler out of that bundle. New slices
(commands or queries) add a new field on `TrustHandlers` and a single
line in this factory.

Cross-cutting decorators applied here mirror Access (composition order
matters — innermost first):

1. `bind(deps)` — bare handler.
2. `with_idempotency` (create-style commands only) — Idempotency-Key
   support (`cora.infrastructure.idempotency`). Wrapped before tracing
   so cache-hits and cache-misses both attribute to the tracing span.
3. `with_tracing` — OTel span around every handler call. Records
   `cora.bc`, `cora.command` / `cora.query` attributes.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.observability import with_tracing
from cora.trust.features import define_zone

_BC = "trust"


@dataclass(frozen=True)
class TrustHandlers:
    """The Trust BC's handler bundle, each closed over SharedDeps.

    Phase 3a only ships `define_zone`. Future fields (activate_zone,
    define_conduit, define_policy, evaluate_policy, get_zone, etc.)
    land per slice.
    """

    define_zone: define_zone.IdempotentHandler


def wire_trust(deps: SharedDeps) -> TrustHandlers:
    """Build the Trust BC handlers from shared dependencies."""
    return TrustHandlers(
        define_zone=with_tracing(
            with_idempotency(
                define_zone.bind(deps),
                deps.idempotency_store,
                command_name="DefineZone",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
            ),
            command_name="DefineZone",
            bc=_BC,
        ),
    )
