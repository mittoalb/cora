"""The `MarkSupplyAvailable` command — intent dataclass for this slice.

`supply_id` is the target Supply aggregate. `reason` is operator-
supplied free text captured on the emitted event for audit (for example,
"operator walkdown confirms LN2 flowing", "control room reports beam
delivered after morning startup"). The principal-id of the invoker
is supplied separately by the application handler at call time.

Trigger source is implicit `Operator` — this slice family is
operator-driven by definition. The `TriggerSource` enum was locked
3-value day one (Operator | Monitor | Auto) so that future Monitor-
driven and Auto-restore slices can land additively without enum
evolution; today only Operator slices exist, and the value is
hardcoded by the decider rather than carried on the command.

## Single-source guard at the decider

`mark_supply_available` accepts ONLY `Unknown` (first-observation
declaration). The `Recovering -> Available` transition has distinct
audit semantics (recovery acknowledgement vs first observation) and
exits exclusively via `restore_supply` (10a-b). Phoebus latched-
alarm precedent: first-observation and recovery-confirmation are
two different operator gestures even though they target the same
`Available` status.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class MarkSupplyAvailable:
    """Operator declares a registered Supply is Available (first observation).

    Single-source: requires Supply to be in `Unknown` status. Strict-
    not-idempotent: re-marking an already-Available supply raises.
    """

    supply_id: UUID
    reason: str
