"""Evolver: replay events to reconstruct Plan state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `PlanEvent` without a matching match arm here. (Single
event type today; 6e-2 will add `PlanVersioned` and `PlanDeprecated`.)

Status mapping per event type:
  - `PlanDefined` -> DEFINED  (genesis)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `PracticeDefined → DEFINED` / `MethodDefined →
DEFINED` / `CapabilityDefined → DEFINED` / `SubjectMounted →
MOUNTED` / `ActorDeactivated → is_active=False`.

`asset_ids` is converted from `list[UUID]` (event payload) to
`frozenset[UUID]` (state) here. Order doesn't matter at the state
layer (set semantics for membership / equality); the payload
already sorted in `to_payload` for persistence determinism. Same
precedent as Method's `needs_capabilities`.

The audit snapshots in PlanDefined (method_id,
method_needs_capabilities_snapshot, asset_capabilities_snapshot)
are NOT folded into state — they're audit-only payload data per
gate-review Q4. The evolver intentionally ignores them.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.recipe.aggregates.plan.events import PlanDefined, PlanEvent
from cora.recipe.aggregates.plan.state import Plan, PlanName, PlanStatus


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
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[PlanEvent]) -> Plan | None:
    """Replay a stream of events from the empty initial state."""
    state: Plan | None = None
    for event in events:
        state = evolve(state, event)
    return state
