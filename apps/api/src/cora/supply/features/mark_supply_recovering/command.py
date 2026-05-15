"""The `MarkSupplyRecovering` command — intent dataclass for this slice.

`supply_id` is the target Supply aggregate. `reason` is operator-
supplied free text captured on the emitted event for audit (e.g.,
"beam current detected at 50% nominal", "LN2 dewar refill in
progress", "vacuum pump-down underway"). The principal-id of the
invoker is supplied separately by the application handler at call
time.

## Single-source guard at the decider

`mark_supply_recovering` accepts ONLY `Unavailable`. Recovering is
a transient observation that the underlying resource may be coming
back; it has no meaning unless we were just in Unavailable. Per
the Phoebus latched-alarm pattern, `Recovering -> Available`
requires an explicit `restore_supply` (operator acknowledgement);
this slice is the entry into that latched state.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class MarkSupplyRecovering:
    """Mark a Supply as Recovering (observation suggests it may be coming back)."""

    supply_id: UUID
    reason: str
