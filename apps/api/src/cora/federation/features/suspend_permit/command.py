"""The `SuspendPermit` command: intent dataclass for this slice.

`permit_id` is the target Permit aggregate. `reason` is operator-
supplied free text captured at the API boundary for audit-log
breadcrumb purposes (for example, "peer facility paused outbound
sharing pending PII review", "credential rotation in progress").
Today `reason` is accepted but not threaded onto the emitted
`PermitSuspended` event; the event payload is identity-only
(`permit_id`, `suspended_by_actor_id`, `occurred_at`) and operator
context is preserved on the surrounding `DecisionRegistered` audit
trail. Carrying the field on the command keeps the call shape
forward-compatible for a future event-payload widening without
breaking REST/MCP callers.

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
