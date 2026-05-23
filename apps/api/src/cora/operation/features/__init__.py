"""Vertical slices for the Operation BC.

Slices:
  - `register_procedure` (genesis -> Defined; create-style,
    idempotency-wrapped)
  - `get_procedure` (read; fold-on-read)

FSM-closure transitions:
  - `start_procedure` (Defined -> Running; with ProcedureStartContext
    pre-loading target Assets and rejecting Decommissioned, mirroring
    RunStartContext from the Run BC)
  - `complete_procedure` (Running -> Completed; happy path)
  - `abort_procedure` (Running -> Aborted; emergency exit with reason)

Per-step logbook slice:
  - `append_procedure_step` (entry-shape slice; writes one
    Setpoint/Action/Check entry per step to the
    entries_operation_procedure_steps logbook table; mirrors
    append_run_reading from the Run BC, with lazy-open envelope event
    `ProcedureStepsLogbookOpened` on first append)

Partial-data terminal (triggers the `make_procedure_update_handler`
factory hoist at rule-of-three since
this is the third update slice):
  - `truncate_procedure` (Running -> Truncated; partial-data terminal
    mirroring RunTruncated; reason + optional interrupted_at)

Read side:
  - projection (`proj_operation_procedure_summary`) + `list_procedures`
    (cursor-paginated; status / kind / parent_run_id / target_asset_id
    filters)
  - Held / Resumed only if pilot operator feedback surfaces a need
"""

from cora.operation.features import (
    abort_procedure,
    append_procedure_step,
    complete_procedure,
    get_procedure,
    list_procedures,
    register_procedure,
    start_procedure,
    truncate_procedure,
)

__all__ = [
    "abort_procedure",
    "append_procedure_step",
    "complete_procedure",
    "get_procedure",
    "list_procedures",
    "register_procedure",
    "start_procedure",
    "truncate_procedure",
]
