"""Slice-local cross-aggregate context for `bind_plan_role`.

Threads the Plan's bound Method and the candidate Asset into the
pure decider so the decider stays I/O-free. Same shape as
`PlanWireContext` from `add_plan_wire` but narrower (one Method +
one Asset, not arbitrary asset_ids).

`method` MAY be None when the Plan's `state.method_id` is None: that
would be a legacy Plan whose define-time event lacked the field, and
the decider treats this as `MethodNotFoundError` rather than a silent
permissive path (Plans in current code always carry method_id; the
None branch exists only for evolver back-compat on the state side).
"""

from dataclasses import dataclass

from cora.equipment.aggregates.asset import Asset
from cora.recipe.aggregates.method import Method


@dataclass(frozen=True)
class BindPlanRoleContext:
    """Cross-aggregate inputs the bind_plan_role decider needs."""

    method: Method | None
    asset: Asset | None
