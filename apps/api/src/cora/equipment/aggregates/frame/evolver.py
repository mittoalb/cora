"""Evolver: replay events to reconstruct Frame state.

Status mapping per event type:
  - `FrameRegistered`        -> ACTIVE  (genesis)
  - `FramePlacementUpdated`  -> (status UNCHANGED; mutates placement)
  - `FrameDecommissioned`    -> DECOMMISSIONED  (terminal)

The status mapping is hardcoded per match arm; the event type IS the
status-change indicator (no status field in event payloads). Same
precedent as Asset / Subject / Family.

`name` IS reconstructed from the payload of `FrameRegistered` (set
at registration, never changes via this aggregate). `parent_frame_id`
IS reconstructed from `FrameRegistered`'s payload and is immutable in
v1 (no `reparent_frame` slice).
`placement_relative_to_parent` is set at registration and mutated by
`FramePlacementUpdated.new_placement`. `supersedes` is set at registration
and is immutable across the lifecycle (no `update_supersedes` slice).

**Critical invariant**: the `FramePlacementUpdated` and `FrameDecommissioned`
arms MUST carry `parent_frame_id`, `name`, and `supersedes` through
from prior state. Constructing `Frame(id=..., placement_relative_to_parent=...)`
without explicitly passing them would reset the other fields. The
`require_state` helper keeps the per-arm bodies short.

Transition events applied to empty state raise ValueError: they can
never appear before `FrameRegistered` in a well-formed stream.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.equipment.aggregates.frame.events import (
    FrameDecommissioned,
    FrameEvent,
    FramePlacementUpdated,
    FrameRegistered,
)
from cora.equipment.aggregates.frame.state import Frame, FrameName, FrameStatus
from cora.infrastructure.evolver import require_state


def evolve(state: Frame | None, event: FrameEvent) -> Frame:
    """Apply one event to the current state."""
    match event:
        case FrameRegistered(
            frame_id=frame_id,
            name=name,
            parent_frame_id=parent_frame_id,
            placement_relative_to_parent=placement,
            supersedes=supersedes,
        ):
            _ = state  # FrameRegistered is the genesis event; prior state ignored
            return Frame(
                id=frame_id,
                name=FrameName(name),
                parent_frame_id=parent_frame_id,
                placement_relative_to_parent=placement,
                supersedes=supersedes,
                status=FrameStatus.ACTIVE,
            )
        case FramePlacementUpdated(new_placement=new_placement):
            prior = require_state(state, "FramePlacementUpdated")
            return Frame(
                id=prior.id,
                name=prior.name,
                parent_frame_id=prior.parent_frame_id,
                placement_relative_to_parent=new_placement,
                supersedes=prior.supersedes,
                status=prior.status,
            )
        case FrameDecommissioned():
            prior = require_state(state, "FrameDecommissioned")
            return Frame(
                id=prior.id,
                name=prior.name,
                parent_frame_id=prior.parent_frame_id,
                placement_relative_to_parent=prior.placement_relative_to_parent,
                supersedes=prior.supersedes,
                status=FrameStatus.DECOMMISSIONED,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[FrameEvent]) -> Frame | None:
    """Replay a stream of events from the empty initial state."""
    state: Frame | None = None
    for event in events:
        state = evolve(state, event)
    return state
