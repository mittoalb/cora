"""The `RestoreSupply` command — intent dataclass for this slice.

`supply_id` is the target Supply aggregate. `reason` is operator-
supplied free text captured on the emitted event for audit (e.g.,
"control room confirms beam stable for 5 minutes", "LN2 dewar
refilled and pressure stable", "vacuum confirmed below target
pressure"). The principal-id of the invoker is supplied separately
by the application handler at call time.

## Single-source guard at the decider — operator acknowledgement

`restore_supply` accepts ONLY `Recovering`. This is the recovery-
acknowledgement event, distinct from `mark_supply_available`
(first-observation declaration). Per the Phoebus latched-alarm and
PackML CLEARING -> RESETTING -> IDLE convention, explicit operator
gesture required for full recovery; auto-timer-confirmed restore
is deferred-with-trigger per Watch item 1 in
[[project_supply_design]].
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RestoreSupply:
    """Operator confirms a Recovering Supply is fully back (Recovering -> Available)."""

    supply_id: UUID
    reason: str
