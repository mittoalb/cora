"""Evolver: replay events to reconstruct Asset state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `AssetEvent` without a matching match arm here.

Lifecycle mapping per event type:
  - `AssetRegistered`              -> COMMISSIONED  (genesis)
  - `AssetActivated`               -> ACTIVE
  - `AssetDecommissioned`          -> DECOMMISSIONED  (3-source guard at decider)
  - `AssetRelocated`               -> (lifecycle UNCHANGED; mutates parent_id only)
  - `AssetMaintenanceEntered`      -> MAINTENANCE
  - `AssetRestoredFromMaintenance` -> ACTIVE
  - `AssetCapabilityAdded`         -> (lifecycle UNCHANGED; inserts into capabilities frozenset)
  - `AssetCapabilityRemoved`       -> (lifecycle UNCHANGED; removes from capabilities frozenset)
  - `AssetDegraded`                -> (lifecycle UNCHANGED; condition -> DEGRADED)
  - `AssetFaulted`                 -> (lifecycle UNCHANGED; condition -> FAULTED)
  - `AssetRestored`                -> (lifecycle UNCHANGED; condition -> NOMINAL)

The lifecycle mapping is hardcoded per match arm — the event type
IS the lifecycle-change indicator (no lifecycle field in event
payloads). Same precedent as Subject / Capability. Condition
mapping follows the same pattern (event type encodes the target
condition; no condition field in payload).

`level` IS reconstructed from the payload of AssetRegistered (set
at registration, never changes; payload-carried by design — see
events.py docstring). `parent_id` IS reconstructed from
AssetRegistered's payload AND mutated by AssetRelocated's
`to_parent_id` field. `capabilities` defaults to empty frozenset on
AssetRegistered (additive-state pattern; existing AssetRegistered
events from before 5f-1 fold cleanly without an upcaster) and is
mutated incrementally by `AssetCapabilityAdded` /
`AssetCapabilityRemoved`.

**Critical invariant**: every transition arm MUST carry
`capabilities` AND `condition` through from prior state. Constructing
`Asset(id=..., name=..., level=..., parent_id=..., lifecycle=...)`
without explicitly passing them would silently WIPE the fields to
their defaults (empty frozenset / NOMINAL). 5f-1 added `capabilities`
with a default solely for additive-state forward compatibility on
genesis events; 5g-b added `condition` for the same reason; transition
arms must explicitly carry both. Pinned by
`test_evolve_<transition>_preserves_capabilities` and
`test_evolve_<transition>_preserves_condition` for each transition.

Transition events applied to empty state raise ValueError: they
can never appear before `AssetRegistered` in a well-formed stream.
The `_require_state` helper keeps the per-arm bodies short
(precedent locked by Subject's evolver in 4c).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.equipment.aggregates.asset.events import (
    AssetActivated,
    AssetCapabilityAdded,
    AssetCapabilityRemoved,
    AssetDecommissioned,
    AssetDegraded,
    AssetEvent,
    AssetFaulted,
    AssetMaintenanceEntered,
    AssetRegistered,
    AssetRelocated,
    AssetRestored,
    AssetRestoredFromMaintenance,
)
from cora.equipment.aggregates.asset.state import (
    Asset,
    AssetCondition,
    AssetLevel,
    AssetLifecycle,
    AssetName,
)


def _require_state(state: Asset | None, event_type: str) -> Asset:
    """Transition events require prior state; empty stream is corruption."""
    if state is None:
        msg = f"{event_type} cannot be applied to empty state"
        raise ValueError(msg)
    return state


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
                # capabilities defaults to empty frozenset; condition
                # defaults to NOMINAL. Additive-state pattern: both
                # default-via-state so pre-5f-1 / pre-5g-b streams fold
                # cleanly without an upcaster.
            )
        case AssetActivated():
            prior = _require_state(state, "AssetActivated")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=AssetLifecycle.ACTIVE,
                condition=prior.condition,
                capabilities=prior.capabilities,
            )
        case AssetDecommissioned():
            prior = _require_state(state, "AssetDecommissioned")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=AssetLifecycle.DECOMMISSIONED,
                condition=prior.condition,
                capabilities=prior.capabilities,
            )
        case AssetRelocated(to_parent_id=to_parent_id):
            # Hierarchy mutation: only parent_id changes; lifecycle / level
            # / name / capabilities / condition carry over from prior state.
            # The from_parent_id and reason fields in the event aren't read
            # here (they're audit metadata; the prior state's parent_id is
            # the source of truth for the read path).
            prior = _require_state(state, "AssetRelocated")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=to_parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                capabilities=prior.capabilities,
            )
        case AssetMaintenanceEntered():
            prior = _require_state(state, "AssetMaintenanceEntered")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=AssetLifecycle.MAINTENANCE,
                condition=prior.condition,
                capabilities=prior.capabilities,
            )
        case AssetRestoredFromMaintenance():
            prior = _require_state(state, "AssetRestoredFromMaintenance")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=AssetLifecycle.ACTIVE,
                condition=prior.condition,
                capabilities=prior.capabilities,
            )
        case AssetCapabilityAdded(capability_id=capability_id):
            # Capability mutation: only `capabilities` changes; lifecycle /
            # level / name / parent_id / condition carry over. Frozenset
            # semantics: adding an already-present id is a no-op AT THE
            # EVOLVER LAYER (the decider's strict-not-idempotent guard
            # enforces "must not already be present" at command time).
            prior = _require_state(state, "AssetCapabilityAdded")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                capabilities=prior.capabilities | {capability_id},
            )
        case AssetCapabilityRemoved(capability_id=capability_id):
            # Mirror of AssetCapabilityAdded. Frozenset difference is a
            # no-op when the id isn't present (decider enforces
            # presence at command time).
            prior = _require_state(state, "AssetCapabilityRemoved")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                capabilities=prior.capabilities - {capability_id},
            )
        case AssetDegraded():
            # Condition mutation: only `condition` changes; everything
            # else carries over. The reason field in the event is audit
            # metadata, not folded into state. Decider's no-op-on-unchanged
            # guard prevents redundant transitions; if one slips through
            # (concurrent writers), this arm idempotently sets DEGRADED.
            prior = _require_state(state, "AssetDegraded")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=AssetCondition.DEGRADED,
                capabilities=prior.capabilities,
            )
        case AssetFaulted():
            prior = _require_state(state, "AssetFaulted")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=AssetCondition.FAULTED,
                capabilities=prior.capabilities,
            )
        case AssetRestored():
            prior = _require_state(state, "AssetRestored")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=AssetCondition.NOMINAL,
                capabilities=prior.capabilities,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[AssetEvent]) -> Asset | None:
    """Replay a stream of events from the empty initial state."""
    state: Asset | None = None
    for event in events:
        state = evolve(state, event)
    return state
