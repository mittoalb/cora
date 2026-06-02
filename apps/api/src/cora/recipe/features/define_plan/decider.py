"""Pure decider for the `DefinePlan` command.

First decider in the codebase that takes upstream aggregate state
as input. Per gate-review Q5: the handler pre-loads Practice,
Method, and bound Assets, hands the loaded entities to this
decider as a `PlanBindingContext`. The decider treats them as
opaque domain data and validates without any I/O. `now` and
`new_id` are injected by the handler from the Clock and IdGenerator
ports.

This pattern is the canonical approach for cross-aggregate
validation in CORA. Second instance shipped in `start_run`
with `RunStartContext` of the same shape. Documented in
CONTRIBUTING.md alongside the eventual-consistency rule.

## Validation order

The decider runs validations in this order; each failure short-
circuits and raises immediately. Order chosen so the most
fundamental issues surface first:

1. State must be None (defensive: stream collision). Raises
   `PlanAlreadyExistsError`. In production this is essentially
   impossible thanks to UUIDv7 ids, but keeps the unmapped raise
   from surfacing as 500 instead of 409.
2. `asset_ids` must be non-empty (structural invariant: a Plan
   without bindings is meaningless). Raises `PlanAssetsRequiredError`.
3. Practice must not be Deprecated. Raises `PracticeDeprecatedError`.
4. Method must not be Deprecated. Raises `MethodDeprecatedError`.
5. No bound Asset may be Decommissioned. Raises
   `AssetDecommissionedError` carrying the offending asset_ids.
6. `union(asset.families) ⊇ method.needed_family_ids`. Raises
   `PlanFamiliesNotSatisfiedError` with the missing family
   ids. Per gate-review Q3: bound-Asset-only check (no hierarchy
   traversal); operators model families at whichever
   granularity makes sense and bind the Assets that carry them.
7. Cross-BC affordance-cover guard. When the bound Method points
   at a Capability template, the union of each bound Asset's
   Family.affordances must cover `Capability.required_affordances`.
   Raises `PlanAffordancesNotSatisfiedError` with the missing
   affordance string values. Skipped when `method.capability_id` is
   None (legacy shape; handler builds context with
   `capability=None`).
8. Name validation (via `PlanName` VO). Raises
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
from typing import TYPE_CHECKING
from uuid import UUID

from cora.equipment.aggregates.asset import AssetLifecycle
from cora.recipe.aggregates.method import MethodStatus

if TYPE_CHECKING:
    from cora.equipment.aggregates.family import Affordance
from cora.recipe.aggregates.plan import (
    AssetDecommissionedError,
    MethodDeprecatedError,
    Plan,
    PlanAffordancesNotSatisfiedError,
    PlanAlreadyExistsError,
    PlanAssetsRequiredError,
    PlanDefined,
    PlanFamiliesNotSatisfiedError,
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
    """Decide the events produced by defining a new plan.

    Invariants:
      - State must be None (genesis-only) -> PlanAlreadyExistsError
      - asset_ids must be non-empty -> PlanAssetsRequiredError
      - Practice must not be Deprecated -> PracticeDeprecatedError
      - Method must not be Deprecated -> MethodDeprecatedError
      - No bound Asset may be Decommissioned
        -> AssetDecommissionedError
      - Union of bound Assets' families must cover Method's
        needed_family_ids -> PlanFamiliesNotSatisfiedError
      - When Method has a Capability, union of bound Families'
        affordances must cover Capability.required_affordances
        -> PlanAffordancesNotSatisfiedError
      - Name must be valid -> InvalidPlanNameError
        (via PlanName VO)
    """
    if state is not None:
        raise PlanAlreadyExistsError(state.id)

    if not command.asset_ids:
        raise PlanAssetsRequiredError("at least one asset_id required")

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
        cap for asset in context.assets.values() for cap in asset.families
    )
    missing = context.method.needed_family_ids - union_capabilities
    if missing:
        raise PlanFamiliesNotSatisfiedError(missing)

    # cross-BC affordance-cover guard. Layered on top of the
    # family-id check: even when every needed Family is bound, the union
    # of those Families' `affordances` must cover the Method's bound
    # Capability.required_affordances. SKIPPED when method.capability_id
    # is None (legacy shape; handler builds context with capability=None).
    if context.capability is not None:
        union_affordances: frozenset[Affordance] = frozenset(
            affordance
            for asset in context.assets.values()
            for family_id in asset.families
            for affordance in context.family_affordances.get(family_id, frozenset())
        )
        missing_affordances = context.capability.required_affordances - union_affordances
        if missing_affordances:
            raise PlanAffordancesNotSatisfiedError(frozenset(a.value for a in missing_affordances))

    name = PlanName(command.name)  # validates + trims; raises InvalidPlanNameError
    return [
        PlanDefined(
            plan_id=new_id,
            name=name.value,
            practice_id=command.practice_id,
            asset_ids=tuple(sorted(command.asset_ids, key=str)),
            method_id=context.method.id,
            method_needed_family_ids_snapshot=tuple(
                sorted(context.method.needed_family_ids, key=str)
            ),
            asset_families_snapshot={
                asset_id: tuple(sorted(context.assets[asset_id].families, key=str))
                for asset_id in sorted(context.assets.keys(), key=str)
            },
            occurred_at=now,
        )
    ]
