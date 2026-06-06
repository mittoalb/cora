"""Evolver: replay events to reconstruct Mount state.

Status mapping per event type:
  - `MountRegistered`     -> ACTIVE  (genesis; installed_asset_id = None)
  - `MountDecommissioned` -> DECOMMISSIONED  (terminal)
  - `MountPlacementUpdated`    -> (status UNCHANGED; mutates placement)
  - `MountAssetInstalled`      -> (status UNCHANGED; sets installed_asset_id)
  - `MountAssetUninstalled`    -> (status UNCHANGED; clears installed_asset_id)

The status mapping is hardcoded per match arm; the event type IS the
status-change indicator (no status field in event payloads). Same
precedent as Frame / Asset / Subject.

`slot_code`, `parent_id`, `drawing` are reconstructed from the
`MountRegistered` payload (set at registration, immutable in v1; no
reparent or rename slices). `placement` is set at registration and
mutated by `MountPlacementUpdated.new_placement`. `installed_asset_id`
is implicitly None at registration and toggled by
`MountAssetInstalled` / `MountAssetUninstalled`.

**Critical invariant**: every transition arm MUST carry the
unchanged fields from prior state. Constructing
`Mount(id=..., placement=..., ...)` without explicitly passing
`drawing` would silently reset it to None (the field's default).
The `require_state` helper keeps the per-arm bodies short.

Transition events applied to empty state raise ValueError: they can
never appear before `MountRegistered` in a well-formed stream.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.equipment.aggregates.mount.events import (
    MountAssetInstalled,
    MountAssetUninstalled,
    MountDecommissioned,
    MountEvent,
    MountPlacementUpdated,
    MountRegistered,
)
from cora.equipment.aggregates.mount.state import Mount, MountStatus, SlotCode
from cora.infrastructure.evolver import require_state


def evolve(state: Mount | None, event: MountEvent) -> Mount:
    """Apply one event to the current state."""
    match event:
        case MountRegistered(
            mount_id=mount_id,
            slot_code=slot_code,
            parent_id=parent_id,
            placement=placement,
            drawing=drawing,
        ):
            _ = state  # MountRegistered is the genesis event; prior state ignored
            return Mount(
                id=mount_id,
                slot_code=SlotCode(slot_code),
                parent_id=parent_id,
                placement=placement,
                drawing=drawing,
                installed_asset_id=None,
                status=MountStatus.ACTIVE,
            )
        case MountDecommissioned():
            prior = require_state(state, "MountDecommissioned")
            return Mount(
                id=prior.id,
                slot_code=prior.slot_code,
                parent_id=prior.parent_id,
                placement=prior.placement,
                drawing=prior.drawing,
                installed_asset_id=prior.installed_asset_id,
                status=MountStatus.DECOMMISSIONED,
            )
        case MountPlacementUpdated(new_placement=new_placement):
            prior = require_state(state, "MountPlacementUpdated")
            return Mount(
                id=prior.id,
                slot_code=prior.slot_code,
                parent_id=prior.parent_id,
                placement=new_placement,
                drawing=prior.drawing,
                installed_asset_id=prior.installed_asset_id,
                status=prior.status,
            )
        case MountAssetInstalled(asset_id=asset_id):
            prior = require_state(state, "MountAssetInstalled")
            return Mount(
                id=prior.id,
                slot_code=prior.slot_code,
                parent_id=prior.parent_id,
                placement=prior.placement,
                drawing=prior.drawing,
                installed_asset_id=asset_id,
                status=prior.status,
            )
        case MountAssetUninstalled():
            prior = require_state(state, "MountAssetUninstalled")
            return Mount(
                id=prior.id,
                slot_code=prior.slot_code,
                parent_id=prior.parent_id,
                placement=prior.placement,
                drawing=prior.drawing,
                installed_asset_id=None,
                status=prior.status,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[MountEvent]) -> Mount | None:
    """Replay a stream of events from the empty initial state."""
    state: Mount | None = None
    for event in events:
        state = evolve(state, event)
    return state
