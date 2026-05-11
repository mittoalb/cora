"""Compose the Run BC's handlers from `SharedDeps`.

`wire_run(deps)` is invoked once from the FastAPI lifespan and the
returned `RunHandlers` bundle is stored on `app.state.run`. Routes
and MCP tools pull their handler out of that bundle.

Cross-cutting decorators applied here mirror Recipe / Equipment /
Trust / Subject / Access (composition order matters — innermost
first):

1. `bind(deps)` — bare handler.
2. `with_idempotency` (create-style commands only) — Idempotency-Key
   support.
3. `with_tracing` — OTel span around every handler call.

Phase 6f-1 ships `start_run` (idempotency-wrapped) and `get_run`
(read side). Subsequent slices land per-phase:
  - 6f-2: Run transitions (complete, abort)
  - 6f-3: Hold/Resume/Stop transitions
  - 6f-4: Truncated terminal
  - 6f-5: First substream (separate infra; not a slice in this bundle)
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.observability import with_tracing
from cora.run.features import get_run, start_run

_BC = "run"


@dataclass(frozen=True)
class RunHandlers:
    """The Run BC's handler bundle, each closed over SharedDeps."""

    start_run: start_run.IdempotentHandler
    get_run: get_run.Handler


def wire_run(deps: SharedDeps) -> RunHandlers:
    """Build the Run BC handlers from shared dependencies."""
    return RunHandlers(
        start_run=with_tracing(
            with_idempotency(
                start_run.bind(deps),
                deps.idempotency_store,
                command_name="StartRun",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
            ),
            command_name="StartRun",
            bc=_BC,
        ),
        get_run=with_tracing(
            get_run.bind(deps),
            command_name="GetRun",
            bc=_BC,
            kind="query",
        ),
    )
