"""Vertical slices for the Operation BC.

Phase 10c-a shipped:
  - `register_procedure` (genesis -> Defined; create-style,
    idempotency-wrapped)
  - `get_procedure` (read; fold-on-read)

Phase 10c-b adds the FSM-closure transitions:
  - `start_procedure` (Defined -> Running; with ProcedureStartContext
    pre-loading target Assets and rejecting Decommissioned, mirroring
    RunStartContext from Run 6f-1)
  - `complete_procedure` (Running -> Completed; happy path)
  - `abort_procedure` (Running -> Aborted; emergency exit with reason)

Phase 10c-b iter 2 added the per-step logbook slice:
  - `append_procedure_step` (entry-shape slice; writes one
    Setpoint/Action/Check entry per step to the
    entries_operation_procedure_steps logbook table; mirrors
    append_run_reading from 6f-5b, with lazy-open envelope event
    `ProcedureStepsLogbookOpened` on first append)

Phase 10c-c iter 1 adds the partial-data terminal (and triggers the
`make_procedure_update_handler` factory hoist at rule-of-three since
this is the third update slice):
  - `truncate_procedure` (Running -> Truncated; partial-data terminal
    mirroring RunTruncated from 6f-4; reason + optional interrupted_at)

Phase 10c-c iter 2 adds the read side:
  - projection + `list_procedures`
  - Held / Resumed only if pilot operator feedback surfaces a need
"""

from cora.operation.features import (
    abort_procedure,
    append_procedure_step,
    complete_procedure,
    get_procedure,
    register_procedure,
    start_procedure,
    truncate_procedure,
)

__all__ = [
    "abort_procedure",
    "append_procedure_step",
    "complete_procedure",
    "get_procedure",
    "register_procedure",
    "start_procedure",
    "truncate_procedure",
]
