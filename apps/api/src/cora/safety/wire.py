"""Compose the Safety BC's handlers from `Kernel`.

`wire_safety(deps)` is invoked once from the FastAPI lifespan and the
returned `SafetyHandlers` bundle is stored on `app.state.safety`.
Routes and MCP tools pull their handler out of that bundle. New slices
add a new field on `SafetyHandlers` and a single line in this factory.

Cross-cutting decorators applied here mirror Access / Trust / Subject
/ Equipment / Supply (composition order matters; innermost first):

  1. `bind(deps)` -- bare handler.
  2. `with_idempotency` (create-style commands only) -- Idempotency-Key
     support. Wrapped before tracing so cache-hits and cache-misses
     both attribute to the tracing span.
  3. `with_tracing` -- OTel span around every handler call. Records
     `cora.bc`, `cora.command` / `cora.query` attributes.

## Wired handlers (11a-a)

  - `register_clearance` (create-style; idempotency-wrapped)
  - `get_clearance`      (query)

11a-b will add the FSM-closure transitions; 11a-c will add expire +
amend + Run.start gating; 11b will add operational-caution slices
(likely on a different aggregate / BC).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing
from cora.safety.features import (
    get_clearance,
    register_clearance,
)

_BC = "safety"


@dataclass(frozen=True)
class SafetyHandlers:
    """The Safety BC's handler bundle, each closed over Kernel.

    11a-a: `register_clearance` (create-style; idempotency-wrapped) +
    `get_clearance` (query). Subsequent sub-phases extend the bundle.
    """

    register_clearance: register_clearance.IdempotentHandler
    get_clearance: get_clearance.Handler


def wire_safety(deps: Kernel) -> SafetyHandlers:
    """Build the Safety BC handlers from shared dependencies."""
    return SafetyHandlers(
        register_clearance=with_tracing(
            with_idempotency(
                register_clearance.bind(deps),
                deps.idempotency_store,
                command_name="RegisterClearance",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterClearance",
            bc=_BC,
        ),
        get_clearance=with_tracing(
            get_clearance.bind(deps),
            command_name="GetClearance",
            bc=_BC,
            kind="query",
        ),
    )
