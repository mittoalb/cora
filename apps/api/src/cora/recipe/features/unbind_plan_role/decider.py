"""Pure decider for the `UnbindPlanRole` command.

Invariants:
  - State must not be None -> PlanNotFoundError
  - Plan must be in Defined status -> PlanCannotMutateRoleBindingsError
    (mirrors bind side)
  - role_name must be in state.role_bindings (strict-not-idempotent)
    -> PlanRoleNotBoundError

NOTE: unbind does NOT check whether any Wire depends on the role's
required_ports. If wires reference a port that the now-unbound role
required, they become orphan-but-valid; any subsequent `add_plan_wire`
will catch the inconsistency via `PlanWireRoleEndpointMismatchError`.
A pro-active wire-dependency-on-unbind check is a watch-item, not a
v1 invariant per [[project-plan-role-bindings-design]] open questions.
"""

from datetime import datetime

from cora.recipe.aggregates.plan import (
    Plan,
    PlanCannotMutateRoleBindingsError,
    PlanNotFoundError,
    PlanRoleNotBoundError,
    PlanRoleUnbound,
    PlanStatus,
)
from cora.recipe.features.unbind_plan_role.command import UnbindPlanRole


def decide(
    state: Plan | None,
    command: UnbindPlanRole,
    *,
    now: datetime,
) -> list[PlanRoleUnbound]:
    """Decide the events produced by unbinding a role."""
    if state is None:
        raise PlanNotFoundError(command.plan_id)

    if state.status is not PlanStatus.DEFINED:
        raise PlanCannotMutateRoleBindingsError(state.id, state.status)

    if not any(b.role_name == command.role_name for b in state.role_bindings):
        raise PlanRoleNotBoundError(state.id, command.role_name)

    return [
        PlanRoleUnbound(
            plan_id=state.id,
            role_name=command.role_name.value,
            occurred_at=now,
        )
    ]
