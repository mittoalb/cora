"""Evolver: replay events to reconstruct Conduit state.

Mirror of `cora/trust/aggregates/zone/evolver.py`. The terminal
`assert_never` case forces pyright (and the runtime) to error if a
new event type is added to `ConduitEvent` without a matching match
arm.

Phase 6f-5a adds two channel-lifecycle event arms:
  - `ConduitChannelOpened` adds the channel id to `open_channels`
  - `ConduitChannelClosed` removes it

Defensive guards: both arms raise on `state is None` (the parent
Conduit must exist before any channel can attach to it). The
open-arm raises if the channel id is already in `open_channels`
(should be impossible in a clean stream; signals contamination);
the close-arm raises if the id is not in `open_channels`
(symmetric).
"""

from collections.abc import Sequence
from dataclasses import replace
from typing import assert_never

from cora.trust.aggregates.conduit.events import (
    ConduitChannelClosed,
    ConduitChannelOpened,
    ConduitDefined,
    ConduitEvent,
)
from cora.trust.aggregates.conduit.state import (
    Conduit,
    ConduitChannelAlreadyOpenError,
    ConduitChannelNotOpenError,
    ConduitName,
)


def evolve(state: Conduit | None, event: ConduitEvent) -> Conduit:
    """Apply one event to the current state."""
    match event:
        case ConduitDefined(
            conduit_id=conduit_id,
            name=name,
            source_zone_id=source_zone_id,
            target_zone_id=target_zone_id,
        ):
            _ = state  # ConduitDefined is the genesis event; prior state ignored
            return Conduit(
                id=conduit_id,
                name=ConduitName(name),
                source_zone_id=source_zone_id,
                target_zone_id=target_zone_id,
            )
        case ConduitChannelOpened(channel_id=channel_id):
            if state is None:
                msg = "ConduitChannelOpened before ConduitDefined: stream is corrupted"
                raise ValueError(msg)
            if channel_id in state.open_channels:
                raise ConduitChannelAlreadyOpenError(state.id, channel_id)
            return replace(state, open_channels=state.open_channels | {channel_id})
        case ConduitChannelClosed(channel_id=channel_id):
            if state is None:
                msg = "ConduitChannelClosed before ConduitDefined: stream is corrupted"
                raise ValueError(msg)
            if channel_id not in state.open_channels:
                raise ConduitChannelNotOpenError(state.id, channel_id)
            return replace(state, open_channels=state.open_channels - {channel_id})
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[ConduitEvent]) -> Conduit | None:
    """Replay a stream of events from the empty initial state."""
    state: Conduit | None = None
    for event in events:
        state = evolve(state, event)
    return state
