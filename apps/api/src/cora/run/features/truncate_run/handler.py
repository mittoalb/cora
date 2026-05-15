"""Application handler for the `truncate_run` slice.

Update-style handler. Canonical body lives in
`cora.run._update_handler.make_run_update_handler`; this module
is a thin slice-specific bind.

The command's `reason` and `interrupted_at` fields are captured
on the emitted `RunTruncated` event payload but are intentionally
NOT logged at the handler boundary (matches stop_run / abort_run
/ Subject discard / Asset condition precedent). Pre-hoist this
slice logged `interrupted_at` on the `start` line only — an
asymmetric afterthought, not a designed log shape; aligned away
during the cross-BC update-handler hoist.

## Per-event grouping note (gate-review L11)

This handler emits one event today (`RunTruncated`); when the Run
aggregate gains logbooks (6f-5b/c), it will emit one
`RunLogbookClosed` per open logbook before the `RunTruncated`. All
events from one truncate command share:
  - the same `correlation_id` (the OTel trace_id)
  - `metadata.command = "TruncateRun"`
  - contiguous stream version order

Auditors group events from one truncate by `correlation_id` plus
`metadata.command`, NOT by `causation_id` (which is None for top-
level commands from REST/MCP).

## Liveness gap (gate-review L4-followup)

`truncate_run` is the cleanup mechanism for known-dead Runs; it
does NOT detect them. A Run that was interrupted on Saturday and
nobody truncates is still RUNNING in the FSM until an operator
calls truncate. Stale-RUNNING detection is a separate liveness
concern (heartbeat / projection-worker territory) and is out of
scope for 6f-4.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.run._update_handler import make_run_update_handler
from cora.run.features.truncate_run.command import TruncateRun
from cora.run.features.truncate_run.decider import decide


class Handler(Protocol):
    """Callable interface every truncate_run handler implements."""

    async def __call__(
        self,
        command: TruncateRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a truncate_run handler closed over the shared deps."""
    return make_run_update_handler(
        deps,
        command_name="TruncateRun",
        log_prefix="truncate_run",
        decide_fn=decide,
    )
