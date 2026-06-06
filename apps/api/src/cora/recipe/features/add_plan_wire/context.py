"""Cross-aggregate context the `add_plan_wire` decider validates against.

`PlanWireContext` is built by the `add_plan_wire` handler from
`load_asset` calls before reaching the pure decider. The decider
treats the loaded Asset entities as opaque domain data and
validates the wire's port-existence + direction + signal_type
without performing any I/O.

Pattern: same shape as `PlanBindingContext` (6e-1) and
`RunStartContext` (6f-1). Slice-local module by design — promote
to a shared form only after the rule of three (and only if the
shape really matches across slices).

The handler loads the two Assets referenced by the wire's source +
target asset_ids (deduplicated when source == target, which is
allowed for non-degenerate self-loops between distinct ports on
the same Asset). The handler does NOT load every Asset bound by
the Plan — only those the proposed wire references. The bound-set
membership check uses `state.asset_ids` directly (no Asset load
needed for that branch).
"""

from dataclasses import dataclass, field
from uuid import UUID

from cora.equipment.aggregates.asset import Asset
from cora.recipe.aggregates.method import Method


@dataclass(frozen=True)
class PlanWireContext:
    """Snapshot of upstream Asset state at wire-validation time.

    `assets` is the loaded set of Asset instances the proposed wire
    references, keyed by `asset_id`. Always contains entries for
    BOTH endpoint asset_ids (deduplicated when source == target).
    May be empty if the proposed wire's asset_ids aren't bound by
    the Plan: the decider rejects with `PlanWireAssetNotBoundError`
    before consulting the context, so the validators never see
    missing keys.

    `method` is the Plan's bound Method (loaded by the handler via
    state.method_id) when present. The role-endpoint check walks
    `method.required_roles` to enforce the structural closure between
    Plan.role_bindings and Plan.wires (see
    `PlanWireRoleEndpointMismatchError`). None when state.method_id
    is None (Plan with no Method binding) OR when the test passes a
    context without a method.
    """

    assets: dict[UUID, Asset]
    method: Method | None = field(default=None)
