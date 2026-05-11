"""Pure decider for the `DefineCapability` command.

Pure function: given the current Capability state (None for a fresh
stream) and a `DefineCapability` command, returns the events to
append. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports.
"""

from datetime import datetime
from uuid import UUID

from cora.equipment.aggregates.capability import (
    Capability,
    CapabilityAlreadyExistsError,
    CapabilityDefined,
    CapabilityName,
)
from cora.equipment.features.define_capability.command import DefineCapability


def decide(
    state: Capability | None,
    command: DefineCapability,
    *,
    now: datetime,
    new_id: UUID,
) -> list[CapabilityDefined]:
    """Decide the events produced by defining a new capability."""
    if state is not None:
        raise CapabilityAlreadyExistsError(state.id)
    name = CapabilityName(command.name)  # validates + trims; raises InvalidCapabilityNameError
    return [
        CapabilityDefined(
            capability_id=new_id,
            name=name.value,
            occurred_at=now,
        )
    ]
