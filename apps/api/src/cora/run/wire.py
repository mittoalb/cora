"""Compose the Run BC's handlers from `Kernel`.

`wire_run(deps)` is invoked once from the FastAPI lifespan and the
returned `RunHandlers` bundle is stored on `app.state.run`. Routes
and MCP tools pull their handler out of that bundle.

Cross-cutting decorators applied here mirror Recipe / Equipment /
Trust / Subject / Access (composition order matters — innermost
first):

1. `bind(deps)` — bare handler.
2. `with_idempotency` (create-style commands only) — Idempotency-Key
   support. Transition handlers (complete / abort / hold / resume /
   stop) do NOT idempotency-wrap: they're update-style, the strict-
   not-idempotent guard already rejects double-application, and the
   ConcurrencyError on stale expected_version handles the
   double-submit case at the persistence layer.
3. `with_tracing` — OTel span around every handler call.

Phase 6f-1 shipped `start_run` (idempotency-wrapped) + `get_run`
(read side). Phase 6f-2 added `complete_run` + `abort_run` (terminal
transitions). Phase 6f-3 added `hold_run` + `resume_run` + `stop_run`
(the bidirectional pause cycle plus the controlled-exit terminal).
Phase 6f-4 closes the FSM with `truncate_run` (partial-data terminal
for known-dead Runs being closed retroactively).

Subsequent slices land per-phase:
  - 6f-5: First observation channels for Run (separate infra; not a slice in this bundle)
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing
from cora.run.features import (
    abort_run,
    complete_run,
    get_run,
    hold_run,
    resume_run,
    start_run,
    stop_run,
    truncate_run,
)

_BC = "run"


@dataclass(frozen=True)
class RunHandlers:
    """The Run BC's handler bundle, each closed over Kernel."""

    start_run: start_run.IdempotentHandler
    complete_run: complete_run.Handler
    abort_run: abort_run.Handler
    hold_run: hold_run.Handler
    resume_run: resume_run.Handler
    stop_run: stop_run.Handler
    truncate_run: truncate_run.Handler
    get_run: get_run.Handler


def wire_run(deps: Kernel) -> RunHandlers:
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
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="StartRun",
            bc=_BC,
        ),
        complete_run=with_tracing(
            complete_run.bind(deps),
            command_name="CompleteRun",
            bc=_BC,
        ),
        abort_run=with_tracing(
            abort_run.bind(deps),
            command_name="AbortRun",
            bc=_BC,
        ),
        hold_run=with_tracing(
            hold_run.bind(deps),
            command_name="HoldRun",
            bc=_BC,
        ),
        resume_run=with_tracing(
            resume_run.bind(deps),
            command_name="ResumeRun",
            bc=_BC,
        ),
        stop_run=with_tracing(
            stop_run.bind(deps),
            command_name="StopRun",
            bc=_BC,
        ),
        truncate_run=with_tracing(
            truncate_run.bind(deps),
            command_name="TruncateRun",
            bc=_BC,
        ),
        get_run=with_tracing(
            get_run.bind(deps),
            command_name="GetRun",
            bc=_BC,
            kind="query",
        ),
    )
