"""Pure decider for the `DefineFamily` command.

Pure function: given the current Family state (None for a fresh
stream) and a `DefineFamily` command, returns the events to
append. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports.
"""

from datetime import datetime
from uuid import UUID

from cora.equipment.aggregates.family import (
    Family,
    FamilyAlreadyExistsError,
    FamilyDefined,
    FamilyName,
)
from cora.equipment.features.define_family.command import DefineFamily


def decide(
    state: Family | None,
    command: DefineFamily,
    *,
    now: datetime,
    new_id: UUID,
) -> list[FamilyDefined]:
    """Decide the events produced by defining a new capability."""
    if state is not None:
        raise FamilyAlreadyExistsError(state.id)
    name = FamilyName(command.name)  # validates + trims; raises InvalidFamilyNameError
    return [
        FamilyDefined(
            family_id=new_id,
            name=name.value,
            occurred_at=now,
        )
    ]
