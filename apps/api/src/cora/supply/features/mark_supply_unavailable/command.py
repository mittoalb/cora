"""The `MarkSupplyUnavailable` command — intent dataclass for this slice.

`supply_id` is the target Supply aggregate. `reason` is operator-
supplied free text captured on the emitted event for audit (e.g.,
"beam dump at 09:32", "LN2 dewar empty", "vacuum loss in sample
chamber"). The principal-id of the invoker is supplied separately
by the application handler at call time.

Trigger source is implicit `Operator` (10a-b only). Substream-driven
`Monitor` slices and timer-driven `Auto` slices are deferred-with-
trigger.

## Multi-source guard at the decider (widest source set)

`mark_supply_unavailable` accepts the widest source set of any
Supply transition: `{Unknown, Available, Degraded, Recovering}`.
Anything that's not already Unavailable or terminal can become
Unavailable. Strict-not-idempotent: re-marking an already-
Unavailable supply raises.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class MarkSupplyUnavailable:
    """Mark a Supply as Unavailable (resource is down)."""

    supply_id: UUID
    reason: str
