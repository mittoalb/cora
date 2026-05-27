"""The `DeregisterSupply` command - intent dataclass for this slice.

`supply_id` is the target Supply aggregate. `reason` is operator-
supplied free text captured on the emitted event for audit (for example,
"typo on scope at registration; re-registering correctly", "beamline
retired", "duplicate of supply <id>"). The principal-id of the
invoker is supplied separately by the application handler at call time.

Trigger source is implicit `Operator` (never `Monitor` or `Auto`). No
substream or timer logic should ever auto-decommission a Supply; the
shape mirrors the in-BC pattern where transition commands omit
`trigger` entirely and the decider hardcodes the value.

## Source-state guard (widest of any Supply transition)

`deregister_supply` accepts any non-Decommissioned status: Unknown,
Available, Degraded, Unavailable, or Recovering. Strict-not-idempotent:
re-issuing on an already-Decommissioned supply raises a 409 with the
current status in the diagnostic message.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DeregisterSupply:
    """Deregister a Supply (lifecycle terminal: any -> Decommissioned)."""

    supply_id: UUID
    reason: str
