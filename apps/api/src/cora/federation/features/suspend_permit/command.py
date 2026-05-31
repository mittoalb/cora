"""The `SuspendPermit` command: intent dataclass for this slice.

`permit_id` is the target Permit aggregate. `reason` is operator-
supplied free text captured at the API boundary for audit-log
breadcrumb purposes (for example, "peer facility paused outbound
sharing pending PII review", "credential rotation in progress").
`reason` flows through to the emitted `PermitSuspended` event payload
so operator context survives on the immutable event log alongside
the surrounding `DecisionRegistered` audit trail.

The principal-id of the invoker is supplied separately by the
application handler at call time.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class SuspendPermit:
    """Operator suspends an Active Permit (Active -> Suspended)."""

    permit_id: UUID
    reason: str | None = None
