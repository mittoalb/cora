"""Evolver: replay events to reconstruct Plan state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `PlanEvent` without a matching match arm here.

Status mapping per event type:
  - `PlanDefined`    -> DEFINED   (genesis; version=None)
  - `PlanVersioned`  -> VERSIONED (version=event.version_tag;
                                    multi-source: Defined | Versioned)
  - `PlanDeprecated` -> DEPRECATED (version preserved;
                                    multi-source: Defined | Versioned)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `PracticeDefined → DEFINED` / `MethodDefined →
DEFINED` / `CapabilityDefined → DEFINED` / `SubjectMounted →
MOUNTED` / `ActorDeactivated → is_active=False`. Mirrors Practice's
transition evolver shape from Recipe 6d-2.

`asset_ids` is converted from `list[UUID]` (event payload) to
`frozenset[UUID]` (state) here. Order doesn't matter at the state
layer (set semantics for membership / equality); the payload
already sorted in `to_payload` for persistence determinism. Same
precedent as Method's `needs_capabilities`.

`version` is mutated by PlanVersioned (set to the new tag) and
PRESERVED by PlanDeprecated as the audit signal of the last revision
before deprecation. Pre-6e-2 PlanDefined-only streams fold cleanly
with version=None (the additive-state pattern).

The audit snapshots in PlanDefined (method_id,
method_needs_capabilities_snapshot, asset_capabilities_snapshot)
are NOT folded into state — they're audit-only payload data per
gate-review Q4. The evolver intentionally ignores them.

**Critical invariant**: every transition arm MUST carry
`practice_id`, `asset_ids`, AND `version` through from prior state.
Constructing `Plan(id=..., name=..., status=...)` without explicitly
passing the carry-through fields would silently change them. The
transition arms explicitly pass each.

Transition events applied to empty state raise ValueError: they can
never appear before `PlanDefined` in a well-formed stream. The
`_require_state` helper keeps per-arm bodies short (precedent locked
by Subject's evolver in 4c).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.recipe.aggregates.plan.events import (
    PlanDefined,
    PlanDeprecated,
    PlanEvent,
    PlanVersioned,
)
from cora.recipe.aggregates.plan.state import Plan, PlanName, PlanStatus


def _require_state(state: Plan | None, event_type: str) -> Plan:
    """Transition events require prior state; empty stream is corruption."""
    if state is None:
        msg = f"{event_type} cannot be applied to empty state"
        raise ValueError(msg)
    return state


def evolve(state: Plan | None, event: PlanEvent) -> Plan:
    """Apply one event to the current state."""
    match event:
        case PlanDefined(
            plan_id=plan_id,
            name=name,
            practice_id=practice_id,
            asset_ids=asset_ids,
        ):
            _ = state  # PlanDefined is the genesis event; prior state ignored.
            # Audit-only payload fields (method_id, snapshots) deliberately
            # not destructured — slim aggregate doesn't fold them.
            return Plan(
                id=plan_id,
                name=PlanName(name),
                practice_id=practice_id,
                asset_ids=frozenset(asset_ids),
                status=PlanStatus.DEFINED,
                # version defaults to None.
            )
        case PlanVersioned(version_tag=version_tag):
            prior = _require_state(state, "PlanVersioned")
            return Plan(
                id=prior.id,
                name=prior.name,
                practice_id=prior.practice_id,
                asset_ids=prior.asset_ids,
                status=PlanStatus.VERSIONED,
                version=version_tag,
            )
        case PlanDeprecated():
            prior = _require_state(state, "PlanDeprecated")
            return Plan(
                id=prior.id,
                name=prior.name,
                practice_id=prior.practice_id,
                asset_ids=prior.asset_ids,
                status=PlanStatus.DEPRECATED,
                # version preserved across deprecation.
                version=prior.version,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[PlanEvent]) -> Plan | None:
    """Replay a stream of events from the empty initial state."""
    state: Plan | None = None
    for event in events:
        state = evolve(state, event)
    return state
