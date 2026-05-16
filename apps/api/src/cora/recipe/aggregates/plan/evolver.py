"""Evolver: replay events to reconstruct Plan state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `PlanEvent` without a matching match arm here.

Status mapping per event type:
  - `PlanDefined`                  -> DEFINED   (genesis; version=None,
                                                  default_parameters={};
                                                  wires=frozenset();
                                                  method_id read from payload)
  - `PlanVersioned`                -> VERSIONED (version=event.version_tag;
                                                  multi-source: Defined | Versioned)
  - `PlanDeprecated`               -> DEPRECATED (version preserved;
                                                  multi-source: Defined | Versioned)
  - `PlanDefaultParametersUpdated` -> status preserved (orthogonal to
                                                  lifecycle; updates the
                                                  default_parameters field
                                                  with the post-merge dict; 6g-b)
  - `PlanWireAdded`                -> status preserved (orthogonal to
                                                  lifecycle; adds a Wire to
                                                  state.wires; 6h)
  - `PlanWireRemoved`              -> status preserved (orthogonal to
                                                  lifecycle; removes a Wire
                                                  from state.wires; 6h)

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

The audit snapshots in PlanDefined
(method_needs_capabilities_snapshot, asset_capabilities_snapshot)
are NOT folded into state — they're audit-only payload data per
gate-review Q4. The evolver intentionally ignores them.

`method_id` was originally in that audit-only set; promoted to
state in 6g-b because the `update_plan_default_parameters` decider
needs it to look up `Method.parameters_schema` (per the slim-aggregate
escape clause: state holds what future deciders need). Pre-6g-b
PlanDefined streams fold cleanly because `method_id` was already
in the payload from day one.

**Critical invariant**: every transition arm MUST carry
`practice_id`, `asset_ids`, `version`, `method_id`,
`default_parameters`, AND `wires` through from prior state.
Constructing `Plan(id=..., name=..., status=...)` without
explicitly passing the carry-through fields would silently change
them. The transition arms explicitly pass each.

Transition events applied to empty state raise ValueError: they can
never appear before `PlanDefined` in a well-formed stream. The
`require_state` helper keeps per-arm bodies short (precedent locked
by Subject's evolver in 4c).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.infrastructure.evolver import require_state
from cora.recipe.aggregates.plan.events import (
    PlanDefaultParametersUpdated,
    PlanDefined,
    PlanDeprecated,
    PlanEvent,
    PlanVersioned,
    PlanWireAdded,
    PlanWireRemoved,
)
from cora.recipe.aggregates.plan.state import Plan, PlanName, PlanStatus, Wire


def evolve(state: Plan | None, event: PlanEvent) -> Plan:
    """Apply one event to the current state."""
    match event:
        case PlanDefined(
            plan_id=plan_id,
            name=name,
            practice_id=practice_id,
            asset_ids=asset_ids,
            method_id=method_id,
        ):
            _ = state  # PlanDefined is the genesis event; prior state ignored.
            # Audit-only snapshot fields deliberately not destructured —
            # they're payload-only per slim-aggregate principle. method_id
            # IS folded as of 6g-b (decider for default_parameters needs
            # it; see evolver docstring).
            return Plan(
                id=plan_id,
                name=PlanName(name),
                practice_id=practice_id,
                asset_ids=frozenset(asset_ids),
                status=PlanStatus.DEFINED,
                # version defaults to None.
                method_id=method_id,
                # default_parameters defaults to {} via state default.
            )
        case PlanVersioned(version_tag=version_tag):
            prior = require_state(state, "PlanVersioned")
            return Plan(
                id=prior.id,
                name=prior.name,
                practice_id=prior.practice_id,
                asset_ids=prior.asset_ids,
                status=PlanStatus.VERSIONED,
                version=version_tag,
                method_id=prior.method_id,
                default_parameters=prior.default_parameters,
                wires=prior.wires,
            )
        case PlanDeprecated():
            prior = require_state(state, "PlanDeprecated")
            return Plan(
                id=prior.id,
                name=prior.name,
                practice_id=prior.practice_id,
                asset_ids=prior.asset_ids,
                status=PlanStatus.DEPRECATED,
                # version preserved across deprecation.
                version=prior.version,
                method_id=prior.method_id,
                default_parameters=prior.default_parameters,
                wires=prior.wires,
            )
        case PlanDefaultParametersUpdated(default_parameters=default_parameters):
            prior = require_state(state, "PlanDefaultParametersUpdated")
            return Plan(
                id=prior.id,
                name=prior.name,
                practice_id=prior.practice_id,
                asset_ids=prior.asset_ids,
                status=prior.status,
                version=prior.version,
                method_id=prior.method_id,
                default_parameters=default_parameters,
                wires=prior.wires,
            )
        case PlanWireAdded(
            source_asset_id=source_asset_id,
            source_port_name=source_port_name,
            target_asset_id=target_asset_id,
            target_port_name=target_port_name,
        ):
            prior = require_state(state, "PlanWireAdded")
            new_wire = Wire(
                source_asset_id=source_asset_id,
                source_port_name=source_port_name,
                target_asset_id=target_asset_id,
                target_port_name=target_port_name,
            )
            return Plan(
                id=prior.id,
                name=prior.name,
                practice_id=prior.practice_id,
                asset_ids=prior.asset_ids,
                status=prior.status,
                version=prior.version,
                method_id=prior.method_id,
                default_parameters=prior.default_parameters,
                wires=prior.wires | {new_wire},
            )
        case PlanWireRemoved(
            source_asset_id=source_asset_id,
            source_port_name=source_port_name,
            target_asset_id=target_asset_id,
            target_port_name=target_port_name,
        ):
            prior = require_state(state, "PlanWireRemoved")
            removed_wire = Wire(
                source_asset_id=source_asset_id,
                source_port_name=source_port_name,
                target_asset_id=target_asset_id,
                target_port_name=target_port_name,
            )
            return Plan(
                id=prior.id,
                name=prior.name,
                practice_id=prior.practice_id,
                asset_ids=prior.asset_ids,
                status=prior.status,
                version=prior.version,
                method_id=prior.method_id,
                default_parameters=prior.default_parameters,
                wires=prior.wires - {removed_wire},
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[PlanEvent]) -> Plan | None:
    """Replay a stream of events from the empty initial state."""
    state: Plan | None = None
    for event in events:
        state = evolve(state, event)
    return state
