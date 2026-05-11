"""Pure decider for the `DeprecateCapability` command.

Multi-source-state transition: `Defined | Versioned -> Deprecated`.
Same source-set as version_capability but the target is terminal.
Re-deprecating an already-Deprecated capability raises (strict-not-
idempotent).

Source-state guard uses tuple-membership (same precedent as
decommission_asset).

Invariants:
  - State must not be None -> CapabilityNotFoundError
  - State.status must be in {Defined, Versioned}
    -> CapabilityCannotDeprecateError(current_status=...)
"""

from datetime import datetime

from cora.equipment.aggregates.capability import (
    Capability,
    CapabilityCannotDeprecateError,
    CapabilityDeprecated,
    CapabilityNotFoundError,
    CapabilityStatus,
)
from cora.equipment.features.deprecate_capability.command import DeprecateCapability

_DEPRECATABLE_STATUSES: tuple[CapabilityStatus, ...] = (
    CapabilityStatus.DEFINED,
    CapabilityStatus.VERSIONED,
)


def decide(
    state: Capability | None,
    command: DeprecateCapability,
    *,
    now: datetime,
) -> list[CapabilityDeprecated]:
    """Decide the events produced by deprecating an existing capability."""
    if state is None:
        raise CapabilityNotFoundError(command.capability_id)
    if state.status not in _DEPRECATABLE_STATUSES:
        raise CapabilityCannotDeprecateError(state.id, current_status=state.status)
    return [CapabilityDeprecated(capability_id=state.id, occurred_at=now)]
