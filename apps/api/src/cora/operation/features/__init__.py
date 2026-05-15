"""Vertical slices for the Operation BC.

Phase 10c-a ships:
  - `register_procedure` (genesis -> Defined; create-style,
    idempotency-wrapped)
  - `get_procedure` (read; fold-on-read)

Phase 10c-b adds the transition slices + per-step substream:
  - `start_procedure` (Defined -> Running; with ProcedureStartContext
    pre-loading target Assets and reject Decommissioned, mirroring
    RunStartContext from Run 6f-1)
  - `complete_procedure` (Running -> Completed; happy path)
  - `abort_procedure` (Running -> Aborted; emergency exit with reason)
  - `append_procedure_step` (entry-shape slice; writes one
    Setpoint/Action/Check triplet per step to the
    entries_operation_procedure_steps substream; mirrors
    append_run_reading from 6f-5b)

Phase 10c-c adds:
  - `truncate_procedure` (Running -> Truncated; partial-data terminal
    mirroring RunTruncated from 6f-4)
  - projection + `list_procedures`
  - Held / Resumed only if pilot operator feedback surfaces a need
"""

from cora.operation.features import (
    get_procedure,
    register_procedure,
)

__all__ = [
    "get_procedure",
    "register_procedure",
]
