"""Evolver: replay events to reconstruct Conduit state.

Mirror of `cora/trust/aggregates/zone/evolver.py`. The terminal
`assert_never` case forces pyright (and the runtime) to error if a
new event type is added to `ConduitEvent` without a matching match
arm.

Phase 6f-5a adds two channel-lifecycle event arms over the
`channels: dict[str, UUID]` state shape:
  - `ConduitChannelOpened` adds `(kind, channel_id)` to `channels`,
    enforcing the at-most-one-open-per-kind invariant — opening a
    second channel of an existing kind raises
    `ConduitChannelAlreadyOpenError` carrying the existing channel id.
  - `ConduitChannelClosed` finds the kind that owns the closed
    channel id and removes that entry; raises
    `ConduitChannelNotOpenError` if no kind owns the id.

Defensive guards: both arms raise on `state is None` (the parent
Conduit must exist before any channel can attach to it). The
evolver returns a fresh `Conduit` with a new `channels` dict on
every channel-open / channel-close — the dict is never mutated in
place. Frozen dataclass blocks field reassignment but not dict
mutation; the codebase relies on the same evolver-purity discipline
used by every other aggregate.
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
        case ConduitChannelOpened(channel_id=channel_id, kind=kind):
            if state is None:
                msg = "ConduitChannelOpened before ConduitDefined: stream is corrupted"
                raise ValueError(msg)
            existing = state.channels.get(kind)
            if existing is not None:
                raise ConduitChannelAlreadyOpenError(state.id, kind, existing)
            return replace(state, channels={**state.channels, kind: channel_id})
        case ConduitChannelClosed(channel_id=channel_id):
            if state is None:
                msg = "ConduitChannelClosed before ConduitDefined: stream is corrupted"
                raise ValueError(msg)
            matching_kind = next(
                (k for k, v in state.channels.items() if v == channel_id),
                None,
            )
            if matching_kind is None:
                raise ConduitChannelNotOpenError(state.id, channel_id)
            return replace(
                state,
                channels={k: v for k, v in state.channels.items() if k != matching_kind},
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[ConduitEvent]) -> Conduit | None:
    """Replay a stream of events from the empty initial state."""
    state: Conduit | None = None
    for event in events:
        state = evolve(state, event)
    return state
