"""Unit tests for the `unbind_plan_role` slice's pure decider.

Mirror of bind_plan_role's tests. Unbind needs no cross-aggregate
reads; only Plan state + the role_name.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.recipe.aggregates.method import RoleName
from cora.recipe.aggregates.plan import (
    Plan,
    PlanCannotMutateRoleBindingsError,
    PlanName,
    PlanNotFoundError,
    PlanRoleNotBoundError,
    PlanRoleUnbound,
    PlanStatus,
    RoleBinding,
)
from cora.recipe.features import unbind_plan_role
from cora.recipe.features.unbind_plan_role import UnbindPlanRole

_NOW = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)


def _plan(
    *,
    status: PlanStatus = PlanStatus.DEFINED,
    role_bindings: frozenset[RoleBinding] | None = None,
) -> Plan:
    aid = uuid4()
    return Plan(
        id=uuid4(),
        name=PlanName("p"),
        practice_id=uuid4(),
        asset_ids=frozenset({aid}),
        status=status,
        method_id=uuid4(),
        role_bindings=role_bindings if role_bindings is not None else frozenset(),
    )


def _binding(role_name: str = "detector") -> RoleBinding:
    return RoleBinding(role_name=RoleName(role_name), asset_id=uuid4())


@pytest.mark.unit
def test_state_none_raises_plan_not_found() -> None:
    with pytest.raises(PlanNotFoundError):
        unbind_plan_role.decide(
            state=None,
            command=UnbindPlanRole(
                plan_id=uuid4(),
                role_name=RoleName("detector"),
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_status_versioned_raises_cannot_mutate() -> None:
    state = _plan(
        status=PlanStatus.VERSIONED,
        role_bindings=frozenset({_binding()}),
    )
    with pytest.raises(PlanCannotMutateRoleBindingsError):
        unbind_plan_role.decide(
            state=state,
            command=UnbindPlanRole(
                plan_id=state.id,
                role_name=RoleName("detector"),
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_unknown_role_name_raises_not_bound() -> None:
    state = _plan(role_bindings=frozenset({_binding("detector")}))
    with pytest.raises(PlanRoleNotBoundError):
        unbind_plan_role.decide(
            state=state,
            command=UnbindPlanRole(
                plan_id=state.id,
                role_name=RoleName("sample_monitor"),
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_happy_path_emits_plan_role_unbound() -> None:
    bound = _binding("detector")
    state = _plan(role_bindings=frozenset({bound}))
    events = unbind_plan_role.decide(
        state=state,
        command=UnbindPlanRole(
            plan_id=state.id,
            role_name=RoleName("detector"),
        ),
        now=_NOW,
    )
    assert events == [
        PlanRoleUnbound(
            plan_id=state.id,
            role_name="detector",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_lifecycle_guard_fires_before_role_not_found_guard() -> None:
    """Versioned Plan with no bindings should surface lifecycle, not
    role-not-found. Mirrors slice-1 same-shape pin."""
    state = _plan(status=PlanStatus.VERSIONED, role_bindings=frozenset())
    with pytest.raises(PlanCannotMutateRoleBindingsError):
        unbind_plan_role.decide(
            state=state,
            command=UnbindPlanRole(
                plan_id=state.id,
                role_name=RoleName("detector"),
            ),
            now=_NOW,
        )


# unused warning suppression
_ = UUID
