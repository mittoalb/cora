"""The `AbortProcedure` command -- intent dataclass for this slice.

Single-source emergency-exit terminal: `Running -> Aborted`. Carries
operator-supplied free-form `reason` string (1-500 chars after trim;
validated at the API boundary AND defensively at the decider via
`ProcedureAbortReason` VO). Mirrors `AbortRun` exactly.

Why free-form vs. structured taxonomy: same posture as Run BC's
abort-reason. Future-additive when documented re-evaluation triggers
fire (vocabulary convergence, Decision BC adoption, regulated-pilot
audit demand).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AbortProcedure:
    """Mark an existing Procedure as aborted (emergency-exit terminal)."""

    procedure_id: UUID
    reason: str
