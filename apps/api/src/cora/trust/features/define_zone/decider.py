"""Pure decider for the `DefineZone` command.

Pure function: given the current Zone state (None for a fresh stream)
and a `DefineZone` command, returns the events to append. No I/O,
no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports — same shape as `register_actor.decide`.
"""

from datetime import datetime
from uuid import UUID

from cora.trust.aggregates.zone import (
    Zone,
    ZoneAlreadyExistsError,
    ZoneDefined,
    ZoneName,
)
from cora.trust.features.define_zone.command import DefineZone


def decide(
    state: Zone | None,
    command: DefineZone,
    *,
    now: datetime,
    new_id: UUID,
) -> list[ZoneDefined]:
    """Decide the events produced by defining a new zone.

    Invariants:
      - State must be None (defensive AlreadyExists guard against UUID
        collision) -> ZoneAlreadyExistsError
      - Name must be valid -> InvalidZoneNameError (via ZoneName VO)
    """
    if state is not None:
        raise ZoneAlreadyExistsError(state.id)
    name = ZoneName(command.name)  # validates + trims; raises InvalidZoneNameError
    return [
        ZoneDefined(
            zone_id=new_id,
            name=name.value,
            occurred_at=now,
        )
    ]
