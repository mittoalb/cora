"""Compose the Operation BC's handlers from `Kernel`.

`wire_operation(deps)` is invoked once from the FastAPI lifespan and
the returned `OperationHandlers` bundle is stored on
`app.state.operation`. Routes and MCP tools pull their handler out
of that bundle. New slices add a new field on `OperationHandlers`
and a single line in this factory.

Cross-cutting decorators applied here mirror Access / Trust /
Subject / Equipment / Recipe / Run / Data / Decision / Supply
(composition order matters -- innermost first):

1. `bind(deps)` -- bare handler.
2. `with_idempotency` (create-style commands only) -- Idempotency-Key
   support. Wrapped before tracing so cache-hits and cache-misses
   both attribute to the tracing span.
3. `with_tracing` -- OTel span around every handler call. Records
   `cora.bc`, `cora.command` / `cora.query` attributes.

## Wired handlers (10c-a)

  - `register_procedure` (create-style; idempotency-wrapped)
  - `get_procedure` (query)

10c-b will add `start_procedure` + transition handlers + the entry-
shape `append_procedure_step` slice (with the BC-internal StepStore
adapter mirroring Decision's ReasoningStore wiring).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing
from cora.operation.features import (
    get_procedure,
    register_procedure,
)

_BC = "operation"


@dataclass(frozen=True)
class OperationHandlers:
    """The Operation BC's handler bundle, each closed over Kernel.

    10c-a ships register_procedure (create-style; idempotency-wrapped)
    + get_procedure (query). 10c-b adds the transition handlers +
    the entry-shape append_procedure_step slice.
    """

    register_procedure: register_procedure.IdempotentHandler
    get_procedure: get_procedure.Handler


def wire_operation(deps: Kernel) -> OperationHandlers:
    """Build the Operation BC handlers from shared dependencies."""
    return OperationHandlers(
        register_procedure=with_tracing(
            with_idempotency(
                register_procedure.bind(deps),
                deps.idempotency_store,
                command_name="RegisterProcedure",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterProcedure",
            bc=_BC,
        ),
        get_procedure=with_tracing(
            get_procedure.bind(deps),
            command_name="GetProcedure",
            bc=_BC,
            kind="query",
        ),
    )
