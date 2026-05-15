"""The `DegradeSupply` command — intent dataclass for this slice.

`supply_id` is the target Supply aggregate. `reason` is operator-
supplied free text captured on the emitted event for audit (e.g.,
"photon beam at half-current after partial top-up", "LN2 dewar at
20% pressure margin", "compressed-air pressure drop detected"). The
principal-id of the invoker is supplied separately by the
application handler at call time.

Trigger source is implicit `Operator` — this slice family is
operator-driven by definition (10a-b). Substream-driven `Monitor`
slices and timer-driven `Auto` slices are deferred-with-trigger.

## Multi-source guard at the decider

`degrade_supply` accepts `{Unknown, Available, Recovering}`. Note
the absence of `Unavailable`: a Supply that's down can't go directly
to Degraded (must transition via `mark_supply_recovering` first).
Strict-not-idempotent: re-degrading an already-Degraded supply
raises.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DegradeSupply:
    """Mark a Supply as Degraded (resource up but below nominal capacity)."""

    supply_id: UUID
    reason: str
