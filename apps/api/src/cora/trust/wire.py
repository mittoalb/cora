"""Compose the Trust BC's handlers from `Kernel`.

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

from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing
from cora.trust.features import (
    define_conduit,
    define_policy,
    define_zone,
    evaluate_policy,
)

_BC = "trust"


@dataclass(frozen=True)
class TrustHandlers:
    """The Trust BC's handler bundle, each closed over Kernel.

    Phase 3d ships `define_zone` + `define_conduit` + `define_policy` +
    `evaluate_policy` (first Trust query slice). Future fields
    (activate/modify slices, etc.) land per slice.

    `evaluate_policy` is bare (`Handler` not `IdempotentHandler`):
    queries don't mutate state and aren't idempotency-wrapped.
    """

    define_zone: define_zone.IdempotentHandler
    define_conduit: define_conduit.IdempotentHandler
    define_policy: define_policy.IdempotentHandler
    evaluate_policy: evaluate_policy.Handler


def wire_trust(deps: Kernel) -> TrustHandlers:
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
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefineZone",
            bc=_BC,
        ),
        define_conduit=with_tracing(
            with_idempotency(
                define_conduit.bind(deps),
                deps.idempotency_store,
                command_name="DefineConduit",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefineConduit",
            bc=_BC,
        ),
        define_policy=with_tracing(
            with_idempotency(
                define_policy.bind(deps),
                deps.idempotency_store,
                command_name="DefinePolicy",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefinePolicy",
            bc=_BC,
        ),
        evaluate_policy=with_tracing(
            evaluate_policy.bind(deps),
            command_name="EvaluatePolicy",
            bc=_BC,
            kind="query",
        ),
    )
