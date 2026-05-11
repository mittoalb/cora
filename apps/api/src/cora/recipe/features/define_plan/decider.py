"""Pure decider for the `DefinePlan` command.

First decider in the codebase that takes upstream aggregate state
as input. Per gate-review Q5: the handler pre-loads Practice,
Method, and bound Assets, hands the loaded entities to this
decider as a `PlanBindingContext`. The decider treats them as
opaque domain data and validates without any I/O. `now` and
`new_id` are injected by the handler from the Clock and IdGenerator
ports.

This pattern is the canonical approach for cross-aggregate
validation in CORA going forward (Run will follow the same shape).
Documented in CONTRIBUTING.md alongside the eventual-consistency
rule.

## Validation order

The decider runs validations in this order; each failure short-
circuits and raises immediately. Order chosen so the most
fundamental issues surface first:

1. State must be None (defensive: stream collision). Raises
   `PlanAlreadyExistsError`. In production this is essentially
   impossible thanks to UUIDv7 ids, but keeps the unmapped raise
   from surfacing as 500 instead of 409.
2. `asset_ids` must be non-empty (structural invariant: a Plan
   without bindings is meaningless). Raises `InvalidPlanError`.
3. Practice must not be Deprecated. Raises `PracticeDeprecatedError`.
4. Method must not be Deprecated. Raises `MethodDeprecatedError`.
5. No bound Asset may be Decommissioned. Raises
   `AssetDecommissionedError` carrying the offending asset_ids.
6. `union(asset.capabilities) ⊇ method.needs_capabilities`. Raises
   `PlanCapabilitiesNotSatisfiedError` with the missing capability
   ids. Per gate-review Q3: bound-Asset-only check (no hierarchy
   traversal); operators model capabilities at whichever
   granularity makes sense and bind the Assets that carry them.
7. Name validation (via `PlanName` VO). Raises
   `InvalidPlanNameError`. Last because the name is a primitive
   the operator can fix without changing any binding state.

## Determinism

Event payloads carry deterministic orderings (sorted UUID lists,
sorted-key dicts) so two runs with the same inputs produce
byte-identical persisted bytes — required for idempotency-key
hashing. Sort applied here at decider construction AND in
`to_payload` (defense in depth, harmless).
"""

from datetime import datetime
from uuid import UUID

from cora.equipment.aggregates.asset import AssetLifecycle
from cora.recipe.aggregates.method import MethodStatus
from cora.recipe.aggregates.plan import (
    AssetDecommissionedError,
    InvalidPlanError,
    MethodDeprecatedError,
    Plan,
    PlanAlreadyExistsError,
    PlanCapabilitiesNotSatisfiedError,
    PlanDefined,
    PlanName,
    PracticeDeprecatedError,
)
from cora.recipe.aggregates.practice import PracticeStatus
from cora.recipe.features.define_plan.command import DefinePlan
from cora.recipe.features.define_plan.context import PlanBindingContext


def decide(
    state: Plan | None,
    command: DefinePlan,
    *,
    context: PlanBindingContext,
    now: datetime,
    new_id: UUID,
) -> list[PlanDefined]:
    """Decide the events produced by defining a new plan."""
    if state is not None:
        raise PlanAlreadyExistsError(state.id)

    if not command.asset_ids:
        raise InvalidPlanError("at least one asset_id required")

    if context.practice.status is PracticeStatus.DEPRECATED:
        raise PracticeDeprecatedError(context.practice.id)

    if context.method.status is MethodStatus.DEPRECATED:
        raise MethodDeprecatedError(context.method.id)

    decommissioned = sorted(
        (
            asset.id
            for asset in context.assets.values()
            if asset.lifecycle is AssetLifecycle.DECOMMISSIONED
        ),
        key=str,
    )
    if decommissioned:
        raise AssetDecommissionedError(decommissioned)

    # Generator expression keeps the element type inferable as UUID
    # (vs `frozenset().union(*generators)` which infers Unknown | UUID).
    union_capabilities: frozenset[UUID] = frozenset(
        cap for asset in context.assets.values() for cap in asset.capabilities
    )
    missing = context.method.needs_capabilities - union_capabilities
    if missing:
        raise PlanCapabilitiesNotSatisfiedError(missing)

    name = PlanName(command.name)  # validates + trims; raises InvalidPlanNameError
    return [
        PlanDefined(
            plan_id=new_id,
            name=name.value,
            practice_id=command.practice_id,
            asset_ids=sorted(command.asset_ids, key=str),
            method_id=context.method.id,
            method_needs_capabilities_snapshot=sorted(context.method.needs_capabilities, key=str),
            asset_capabilities_snapshot={
                asset_id: sorted(context.assets[asset_id].capabilities, key=str)
                for asset_id in sorted(context.assets.keys(), key=str)
            },
            occurred_at=now,
        )
    ]
