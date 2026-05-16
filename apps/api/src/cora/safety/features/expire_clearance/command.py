"""The `ExpireClearance` command -- intent dataclass for this slice.

`reason` is operator-supplied free text captured on the emitted
`ClearanceExpired` event for audit clarity (e.g., "validity window
elapsed", "operator manually expired after scope-change incident").

The expiring actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event,
per cross-BC `RunAborted` / `ClearanceRejected` precedent.

Operator-action only in 11a-c-2. Auto-expiry on `valid_until` is
deferred per watch #7 in [[project_safety_clearance_design]].
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ExpireClearance:
    """Expire an Active clearance (`Active -> Expired`)."""

    clearance_id: UUID
    reason: str
