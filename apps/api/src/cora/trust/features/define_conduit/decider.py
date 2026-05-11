"""Pure decider for the `DefineConduit` command.

Pure function: given the current Conduit state (None for a fresh
stream) and a `DefineConduit` command, returns the events to append.
No I/O, no awaits, no side effects.

`now`, `new_id`, and `traversals_channel_id` are injected by the
application handler from the Clock and IdGenerator ports. The
decider stays pure.

Does NOT verify that `source_zone_id` / `target_zone_id` reference
existing Zones — see `cora.trust.aggregates.conduit.state` for the
eventual-consistency rationale.

## Auto-opens the traversals observation channel (Phase 6f-5a)

The decider emits TWO events in one append:
  1. `ConduitDefined` (genesis)
  2. `ConduitChannelOpened(kind="traversals", schema=...)` declaring
     the per-decision authz audit channel attached to this Conduit.

This realizes the gate-review L1 lock (per-Conduit traversal channel
scoping) and the L8 lock (channel-open events on the parent's main
stream). The schema declared here is the column shape the
`observations_conduit_traversals` table holds; future schema bumps
emit a fresh `ConduitChannelOpened` with a new channel_id rather
than mutating the existing one.
"""

from datetime import datetime
from uuid import UUID

from cora.infrastructure.channel import ChannelFieldSpec, ChannelSchema
from cora.trust.aggregates.conduit import (
    CHANNEL_KIND_TRAVERSALS,
    Conduit,
    ConduitAlreadyExistsError,
    ConduitChannelOpened,
    ConduitDefined,
    ConduitName,
)
from cora.trust.features.define_conduit.command import DefineConduit

# Schema declaration for the traversals channel. Column shape matches
# the `observations_conduit_traversals` table.
_TRAVERSALS_SCHEMA = ChannelSchema(
    fields={
        "actor_id": ChannelFieldSpec(
            type="uuid",
            description="The principal that issued the command.",
        ),
        "command_name": ChannelFieldSpec(
            type="string",
            description="Cross-BC command name (for example 'StartRun', 'DefinePolicy').",
        ),
        "decision": ChannelFieldSpec(
            type="string",
            description="'Allow' or 'Deny', from the Authorize port result.",
        ),
        "reason": ChannelFieldSpec(
            type="string",
            description="Free-form reason on Deny; null on Allow.",
        ),
    },
    description=(
        "Per-decision authorization audit log for commands traversing this "
        "Conduit. One row per Authorize port call."
    ),
)


def decide(
    state: Conduit | None,
    command: DefineConduit,
    *,
    now: datetime,
    new_id: UUID,
    traversals_channel_id: UUID,
) -> list[ConduitDefined | ConduitChannelOpened]:
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
        ),
        ConduitChannelOpened(
            conduit_id=new_id,
            channel_id=traversals_channel_id,
            kind=CHANNEL_KIND_TRAVERSALS,
            schema=_TRAVERSALS_SCHEMA,
            occurred_at=now,
        ),
    ]
