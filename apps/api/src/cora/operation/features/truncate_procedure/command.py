"""The `TruncateProcedure` command -- intent dataclass for this slice.

Single-source partial-data terminal: `Running -> Truncated`. Cleanup
mechanism for a Procedure that became de-facto dead through
interruption (power loss, process crash, hardware fault, weekend
interruption) and is being closed retroactively by an operator.

Carries operator-supplied free-form `reason` (1-500 chars after trim;
validated at the API boundary AND defensively at the decider via
`ProcedureTruncateReason` VO) and optional `interrupted_at` (the
operator's best guess at when the actual interruption happened).
Mirrors `TruncateRun` from Run BC's 6f-4.

## Truncated vs Aborted

Aborted is an emergency exit while the system is still responsive
(operator presses the abort button while watching it happen).
Truncated is a cleanup mechanism for known-dead Procedures
(operator returns Monday, sees the bakeout's vacuum chamber is
open, marks the Friday-evening crash retroactively). The system
itself does not detect de-facto-dead Procedures; operators must
invoke truncate explicitly.

## Interrupted_at semantics

`interrupted_at` is operator-supplied and optional. When provided,
must not be in the future relative to `now` (defensive guard at the
decider via `InvalidProcedureInterruptedAtError`); the decider does
NOT enforce a lower bound: weekend / overnight interruptions
naturally have `interrupted_at` hours or days before `occurred_at`.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class TruncateProcedure:
    """Cleanup terminal for an interrupted Procedure (Running -> Truncated)."""

    procedure_id: UUID
    reason: str
    interrupted_at: datetime | None = None
