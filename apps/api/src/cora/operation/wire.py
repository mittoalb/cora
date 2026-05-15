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
   support. Transition handlers (start / complete / abort) do NOT
   idempotency-wrap: they're update-style, strict-not-idempotent at
   the decider, and naturally guarded by event-store optimistic
   concurrency. Same convention as Run BC and Supply BC.
3. `with_tracing` -- OTel span around every handler call. Records
   `cora.bc`, `cora.command` / `cora.query` attributes.

## Wired handlers (10c-a + 10c-b)

  - `register_procedure` (create-style; idempotency-wrapped)
  - `start_procedure` (transition; pre-loads target Assets)
  - `complete_procedure` (transition)
  - `abort_procedure` (transition)
  - `get_procedure` (query)

10c-b iter 2 will add `append_procedure_step` for the per-step
substream (with the BC-internal StepStore adapter mirroring
Decision's ReasoningStore wiring).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing
from cora.operation.features import (
    abort_procedure,
    complete_procedure,
    get_procedure,
    register_procedure,
    start_procedure,
)

_BC = "operation"


@dataclass(frozen=True)
class OperationHandlers:
    """The Operation BC's handler bundle, each closed over Kernel.

    10c-a shipped register_procedure (create-style; idempotency-wrapped)
    + get_procedure (query). 10c-b adds the three FSM-closure
    transitions (start / complete / abort). 10c-b iter 2 will add the
    entry-shape append_procedure_step slice.
    """

    register_procedure: register_procedure.IdempotentHandler
    start_procedure: start_procedure.Handler
    complete_procedure: complete_procedure.Handler
    abort_procedure: abort_procedure.Handler
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
        start_procedure=with_tracing(
            start_procedure.bind(deps),
            command_name="StartProcedure",
            bc=_BC,
        ),
        complete_procedure=with_tracing(
            complete_procedure.bind(deps),
            command_name="CompleteProcedure",
            bc=_BC,
        ),
        abort_procedure=with_tracing(
            abort_procedure.bind(deps),
            command_name="AbortProcedure",
            bc=_BC,
        ),
        get_procedure=with_tracing(
            get_procedure.bind(deps),
            command_name="GetProcedure",
            bc=_BC,
            kind="query",
        ),
    )
