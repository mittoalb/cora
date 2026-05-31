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
  - `AssetMaintenanceExited`       -> ACTIVE
  - `AssetFamilyAdded`         -> (lifecycle UNCHANGED; inserts into families frozenset)
  - `AssetFamilyRemoved`       -> (lifecycle UNCHANGED; removes from families frozenset)
  - `AssetDegraded`                -> (lifecycle UNCHANGED; condition -> DEGRADED)
  - `AssetFaulted`                 -> (lifecycle UNCHANGED; condition -> FAULTED)
  - `AssetRestored`                -> (lifecycle UNCHANGED; condition -> NOMINAL)
  - `AssetSettingsUpdated`         -> (lifecycle UNCHANGED; settings -> event.settings)
  - `AssetPortAdded`               -> (lifecycle UNCHANGED; inserts AssetPort into ports frozenset)
  - `AssetPortRemoved`             -> (lifecycle UNCHANGED; removes AssetPort matching name)

The lifecycle mapping is hardcoded per match arm — the event type
IS the lifecycle-change indicator (no lifecycle field in event
payloads). Same precedent as Subject / Family. Condition
mapping follows the same pattern (event type encodes the target
condition; no condition field in payload).

`level` IS reconstructed from the payload of AssetRegistered (set
at registration, never changes; payload-carried by design — see
events.py docstring). `parent_id` IS reconstructed from
AssetRegistered's payload AND mutated by AssetRelocated's
`to_parent_id` field. `families` defaults to empty frozenset on
AssetRegistered (additive-state pattern; existing AssetRegistered
events without the families field fold cleanly without an upcaster) and is
mutated incrementally by `AssetFamilyAdded` /
`AssetFamilyRemoved`.

**Critical invariant**: every transition arm MUST carry
`families` AND `condition` AND `settings` AND `ports` AND
`drawing` through from prior state. Constructing `Asset(id=...,
name=..., level=..., parent_id=..., lifecycle=...)` without
explicitly passing them would silently WIPE the fields to their
defaults (empty frozenset / NOMINAL / empty dict / empty frozenset
/ None). `families` was added with a default solely for additive-
state forward compatibility on genesis events; `condition`,
`settings`, `ports`, and `drawing` followed the same additive
pattern. Transition arms must explicitly carry all five. Pinned
by `test_evolve_<transition>_preserves_capabilities`,
`test_evolve_<transition>_preserves_condition`,
`test_evolve_<transition>_preserves_settings`,
`test_evolve_<transition>_preserves_ports`, and
`test_evolve_<transition>_preserves_drawing` for each transition.

Transition events applied to empty state raise ValueError: they
can never appear before `AssetRegistered` in a well-formed stream.
The `require_state` helper keeps the per-arm bodies short
(precedent locked by Subject's evolver).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.equipment.aggregates.asset.events import (
    AssetActivated,
    AssetDecommissioned,
    AssetDegraded,
    AssetEvent,
    AssetFamilyAdded,
    AssetFamilyRemoved,
    AssetFaulted,
    AssetMaintenanceEntered,
    AssetMaintenanceExited,
    AssetPortAdded,
    AssetPortRemoved,
    AssetRegistered,
    AssetRelocated,
    AssetRestored,
    AssetSettingsUpdated,
)
from cora.equipment.aggregates.asset.state import (
    Asset,
    AssetCondition,
    AssetLevel,
    AssetLifecycle,
    AssetName,
    AssetPort,
    PortDirection,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Asset | None, event: AssetEvent) -> Asset:
    """Apply one event to the current state."""
    match event:
        case AssetRegistered(
            asset_id=asset_id,
            name=name,
            level=level,
            parent_id=parent_id,
            drawing=drawing,
        ):
            _ = state  # AssetRegistered is the genesis event; prior state ignored
            return Asset(
                id=asset_id,
                name=AssetName(name),
                level=AssetLevel(level),
                parent_id=parent_id,
                lifecycle=AssetLifecycle.COMMISSIONED,
                drawing=drawing,
                # families defaults to empty frozenset; condition
                # defaults to NOMINAL. Additive-state pattern: both
                # default-via-state so legacy streams without these
                # fields fold cleanly without an upcaster.
            )
        case AssetActivated():
            prior = require_state(state, "AssetActivated")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=AssetLifecycle.ACTIVE,
                condition=prior.condition,
                families=prior.families,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
            )
        case AssetDecommissioned():
            prior = require_state(state, "AssetDecommissioned")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=AssetLifecycle.DECOMMISSIONED,
                condition=prior.condition,
                families=prior.families,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
            )
        case AssetRelocated(to_parent_id=to_parent_id):
            # Hierarchy mutation: only parent_id changes; lifecycle / level
            # / name / families / condition / settings carry over from
            # prior state. The from_parent_id and reason fields in the
            # event aren't read here (audit metadata; prior state's
            # parent_id is the source of truth for the read path).
            prior = require_state(state, "AssetRelocated")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=to_parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                families=prior.families,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
            )
        case AssetMaintenanceEntered():
            prior = require_state(state, "AssetMaintenanceEntered")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=AssetLifecycle.MAINTENANCE,
                condition=prior.condition,
                families=prior.families,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
            )
        case AssetMaintenanceExited():
            prior = require_state(state, "AssetMaintenanceExited")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=AssetLifecycle.ACTIVE,
                condition=prior.condition,
                families=prior.families,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
            )
        case AssetFamilyAdded(family_id=family_id):
            # Family mutation: only `families` changes; everything
            # else carries over. Frozenset semantics: adding an already-
            # present id is a no-op AT THE EVOLVER LAYER (the decider's
            # strict-not-idempotent guard enforces "must not already be
            # present" at command time).
            prior = require_state(state, "AssetFamilyAdded")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                families=prior.families | {family_id},
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
            )
        case AssetFamilyRemoved(family_id=family_id):
            # Mirror of AssetFamilyAdded. Frozenset difference is a
            # no-op when the id isn't present (decider enforces
            # presence at command time). Settings are NOT auto-purged
            # when a Family is removed (5g-c lock: preserve orphans;
            # the update_asset_settings slice's null-write is the
            # cleanup path).
            prior = require_state(state, "AssetFamilyRemoved")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                families=prior.families - {family_id},
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
            )
        case AssetDegraded():
            # Condition mutation: only `condition` changes; everything
            # else carries over. The reason field in the event is audit
            # metadata, not folded into state. Decider's no-op-on-unchanged
            # guard prevents redundant transitions; if one slips through
            # (concurrent writers), this arm idempotently sets DEGRADED.
            prior = require_state(state, "AssetDegraded")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=AssetCondition.DEGRADED,
                families=prior.families,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
            )
        case AssetFaulted():
            prior = require_state(state, "AssetFaulted")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=AssetCondition.FAULTED,
                families=prior.families,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
            )
        case AssetRestored():
            prior = require_state(state, "AssetRestored")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=AssetCondition.NOMINAL,
                families=prior.families,
                settings=prior.settings,
                ports=prior.ports,
                drawing=prior.drawing,
            )
        case AssetSettingsUpdated(settings=settings):
            # Settings mutation: only `settings` changes. Event payload
            # carries the FULL post-merge dict, so this arm
            # simply replaces. Validation already happened at the handler
            # boundary before append; an event in the stream is by
            # definition validated. Shallow-copy the payload dict into
            # state so mutating either side (state or event payload)
            # can't alias the other (B1 defence).
            prior = require_state(state, "AssetSettingsUpdated")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                families=prior.families,
                settings=dict(settings),
                ports=prior.ports,
                drawing=prior.drawing,
            )
        case AssetPortAdded(
            port_name=port_name,
            direction=direction,
            signal_type=signal_type,
        ):
            # Ports mutation: only `ports` changes; everything else
            # carries over. Frozenset semantics: adding the exact
            # AssetPort tuple twice is a no-op AT THE EVOLVER LAYER;
            # the decider's strict-not-idempotent guard enforces "no
            # port with this name already exists" at command time
            # (which is stricter than tuple equality).
            prior = require_state(state, "AssetPortAdded")
            new_port = AssetPort(
                name=port_name,
                direction=PortDirection(direction),
                signal_type=signal_type,
            )
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                families=prior.families,
                settings=prior.settings,
                ports=prior.ports | {new_port},
                drawing=prior.drawing,
            )
        case AssetPortRemoved(port_name=port_name):
            # Mirror of AssetPortAdded. Removes the port whose `name`
            # matches; AssetPort tuple equality alone wouldn't suffice
            # because we may not know the direction/signal_type at the
            # call site. Use a comprehension to filter by name. The
            # decider enforces "port with this name MUST exist" at
            # command time; the evolver-level filter is forgiving (no
            # error if name not found, since by-design the only
            # producer is the decider that already validated).
            prior = require_state(state, "AssetPortRemoved")
            return Asset(
                id=prior.id,
                name=prior.name,
                level=prior.level,
                parent_id=prior.parent_id,
                lifecycle=prior.lifecycle,
                condition=prior.condition,
                families=prior.families,
                settings=prior.settings,
                ports=frozenset(p for p in prior.ports if p.name != port_name),
                drawing=prior.drawing,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[AssetEvent]) -> Asset | None:
    """Replay a stream of events from the empty initial state."""
    state: Asset | None = None
    for event in events:
        state = evolve(state, event)
    return state
