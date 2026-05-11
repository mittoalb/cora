"""Evolver: replay events to reconstruct Asset state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `AssetEvent` without a matching match arm here.

Lifecycle mapping per event type (5b only ships the genesis event;
5c-5e add the transitions):
  - `AssetRegistered`   -> COMMISSIONED  (genesis)

The lifecycle mapping is hardcoded per match arm — the event type
IS the lifecycle-change indicator (no lifecycle field in event
payloads). Same precedent as Subject / Capability.

`level` IS reconstructed from the payload (set at registration,
never changes; payload-carried by design — see events.py
docstring). `parent_id` IS reconstructed from the payload too;
mutable across `AssetRelocated` later.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.equipment.aggregates.asset.events import AssetEvent, AssetRegistered
from cora.equipment.aggregates.asset.state import (
    Asset,
    AssetLevel,
    AssetLifecycle,
    AssetName,
)


def evolve(state: Asset | None, event: AssetEvent) -> Asset:
    """Apply one event to the current state."""
    match event:
        case AssetRegistered(asset_id=asset_id, name=name, level=level, parent_id=parent_id):
            _ = state  # AssetRegistered is the genesis event; prior state ignored
            return Asset(
                id=asset_id,
                name=AssetName(name),
                level=AssetLevel(level),
                parent_id=parent_id,
                lifecycle=AssetLifecycle.COMMISSIONED,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[AssetEvent]) -> Asset | None:
    """Replay a stream of events from the empty initial state."""
    state: Asset | None = None
    for event in events:
        state = evolve(state, event)
    return state
