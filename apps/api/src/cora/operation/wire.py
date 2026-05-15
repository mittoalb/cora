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

## Wired handlers (10c-a + 10c-b iter 1 + iter 2 + 10c-c iter 1)

  - `register_procedure` (create-style; idempotency-wrapped)
  - `start_procedure` (transition; pre-loads target Assets)
  - `complete_procedure` (transition; via `make_procedure_update_handler` factory)
  - `abort_procedure` (transition; via factory)
  - `truncate_procedure` (transition; via factory; partial-data terminal)
  - `append_procedure_step` (entry-shape; lazy-open + batch append)
  - `get_procedure` (query)

## make_procedure_update_handler factory (10c-c iter 1 hoist)

`complete_procedure` + `abort_procedure` + `truncate_procedure` all
use `cora.operation._procedure_update_handler.make_procedure_update_handler`
under the hood. The factory landed at the rule-of-three trigger
when truncate_procedure became the third update slice; mirrors
`_supply_update_handler` (Supply BC's hoist at 10a-b after 5
transitions) and Run BC's `_update_handler.make_run_update_handler`.

## BC-internal StepStore wiring (mirrors Run BC's ReadingStore at L9)

The 10c-b-iter-2 `append_procedure_step` slice needs a `StepStore`
adapter. Per the per-category-writer pattern locked at gate-review
L8/L9 from 6f-5a (Conduit's TraversalStore), the store is built
LOCALLY here from `deps.pool` (Postgres in production) or as
`InMemoryStepStore` in `app_env=test`. NOT promoted to Kernel fields.
Mirrors how Run BC wires its ReadingStore and Decision BC wires its
ReasoningStore.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing
from cora.operation.aggregates.procedure import (
    InMemoryStepStore,
    PostgresStepStore,
    StepStore,
)
from cora.operation.features import (
    abort_procedure,
    append_procedure_step,
    complete_procedure,
    get_procedure,
    register_procedure,
    start_procedure,
    truncate_procedure,
)

_BC = "operation"


@dataclass(frozen=True)
class OperationHandlers:
    """The Operation BC's handler bundle, each closed over Kernel.

    10c-a shipped register_procedure + get_procedure. 10c-b iter 1
    added the three FSM-closure transitions (start / complete / abort).
    10c-b iter 2 added the entry-shape append_procedure_step slice
    (with BC-internal StepStore adapter for the per-step logbook).
    """

    register_procedure: register_procedure.IdempotentHandler
    start_procedure: start_procedure.Handler
    complete_procedure: complete_procedure.Handler
    abort_procedure: abort_procedure.Handler
    truncate_procedure: truncate_procedure.Handler
    append_procedure_step: append_procedure_step.Handler
    get_procedure: get_procedure.Handler


def wire_operation(deps: Kernel) -> OperationHandlers:
    """Build the Operation BC handlers from shared dependencies."""
    step_store: StepStore = (
        PostgresStepStore(deps.pool) if deps.pool is not None else InMemoryStepStore()
    )
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
        truncate_procedure=with_tracing(
            truncate_procedure.bind(deps),
            command_name="TruncateProcedure",
            bc=_BC,
        ),
        append_procedure_step=with_tracing(
            append_procedure_step.bind(deps, step_store=step_store),
            command_name="AppendProcedureStep",
            bc=_BC,
        ),
        get_procedure=with_tracing(
            get_procedure.bind(deps),
            command_name="GetProcedure",
            bc=_BC,
            kind="query",
        ),
    )
