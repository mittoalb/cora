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

Phase 10c-b iter 2 will add:
  - `append_procedure_step` (entry-shape slice; writes one
    Setpoint/Action/Check entry per step to the
    entries_operation_procedure_steps substream; mirrors
    append_run_reading from 6f-5b, with lazy-open envelope event
    `ProcedureStepsLogbookOpened` on first append)

Phase 10c-c adds:
  - `truncate_procedure` (Running -> Truncated; partial-data terminal
    mirroring RunTruncated from 6f-4)
  - projection + `list_procedures`
  - Held / Resumed only if pilot operator feedback surfaces a need
"""

from cora.operation.features import (
    abort_procedure,
    complete_procedure,
    get_procedure,
    register_procedure,
    start_procedure,
)

__all__ = [
    "abort_procedure",
    "complete_procedure",
    "get_procedure",
    "register_procedure",
    "start_procedure",
]
