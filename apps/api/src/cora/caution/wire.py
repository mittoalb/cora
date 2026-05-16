"""Compose the Caution BC's handlers from `Kernel`.

`wire_caution(deps)` is invoked once from the FastAPI lifespan and
the returned `CautionHandlers` bundle is stored on
`app.state.caution`. Routes and MCP tools pull their handler out of
that bundle. New slices add a new field on `CautionHandlers` and a
single line in this factory.

Cross-cutting decorators applied here mirror Access / Trust /
Subject / Equipment / Supply / Safety:

  1. `bind(deps)` -- bare handler.
  2. `with_idempotency` (create-style commands only) -- Idempotency-
     Key support. Wrapped before tracing so cache-hits and cache-
     misses both attribute to the tracing span.
  3. `with_tracing` -- OTel span around every handler call.

## Wired handlers (11b-a)

  - `register_caution`  (create-style; idempotency-wrapped)
  - `supersede_caution` (cross-aggregate; create-style;
                         idempotency-wrapped)
  - `retire_caution`    (transition; no idempotency wrap)
  - `get_caution`       (query)
"""

from dataclasses import dataclass
from uuid import UUID

from cora.caution.features import (
    get_caution,
    list_cautions,
    register_caution,
    retire_caution,
    supersede_caution,
)
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing

_BC = "caution"


@dataclass(frozen=True)
class CautionHandlers:
    """The Caution BC's handler bundle, each closed over Kernel."""

    register_caution: register_caution.IdempotentHandler
    supersede_caution: supersede_caution.IdempotentHandler
    retire_caution: retire_caution.Handler
    get_caution: get_caution.Handler
    list_cautions: list_cautions.Handler


def wire_caution(deps: Kernel) -> CautionHandlers:
    """Build the Caution BC handlers from shared dependencies."""
    return CautionHandlers(
        register_caution=with_tracing(
            with_idempotency(
                register_caution.bind(deps),
                deps.idempotency_store,
                command_name="RegisterCaution",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterCaution",
            bc=_BC,
        ),
        supersede_caution=with_tracing(
            with_idempotency(
                supersede_caution.bind(deps),
                deps.idempotency_store,
                command_name="SupersedeCaution",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="SupersedeCaution",
            bc=_BC,
        ),
        retire_caution=with_tracing(
            retire_caution.bind(deps),
            command_name="RetireCaution",
            bc=_BC,
        ),
        get_caution=with_tracing(
            get_caution.bind(deps),
            command_name="GetCaution",
            bc=_BC,
            kind="query",
        ),
        list_cautions=with_tracing(
            list_cautions.bind(deps),
            command_name="ListCautions",
            bc=_BC,
            kind="query",
        ),
    )
