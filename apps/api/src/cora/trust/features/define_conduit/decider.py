"""Pure decider for the `DefineConduit` command.

Pure function: given the current Conduit state (None for a fresh
stream) and a `DefineConduit` command, returns the events to append.
No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports.

Does NOT verify that `source_zone_id` / `target_zone_id` reference
existing Zones — see `cora.trust.aggregates.conduit.state` for the
eventual-consistency rationale.
"""

from datetime import datetime
from uuid import UUID

from cora.trust.aggregates.conduit import (
    Conduit,
    ConduitAlreadyExistsError,
    ConduitDefined,
    ConduitName,
)
from cora.trust.features.define_conduit.command import DefineConduit


def decide(
    state: Conduit | None,
    command: DefineConduit,
    *,
    now: datetime,
    new_id: UUID,
) -> list[ConduitDefined]:
    """Decide the events produced by defining a new conduit."""
    if state is not None:
        raise ConduitAlreadyExistsError(state.id)
    name = ConduitName(command.name)  # validates + trims
    return [
        ConduitDefined(
            conduit_id=new_id,
            name=name.value,
            source_zone_id=command.source_zone_id,
            target_zone_id=command.target_zone_id,
            occurred_at=now,
        )
    ]
