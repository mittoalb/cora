"""Property-based tests for `unbind_plan_role.decide` (Recipe BC, slice 2)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

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

if TYPE_CHECKING:
    from datetime import datetime

_VALID_ROLE_NAME = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=50,
)
_NON_DEFINED_STATUS = st.sampled_from([PlanStatus.VERSIONED, PlanStatus.DEPRECATED])
_ANY_DATETIME = st.datetimes()


def _plan(
    *,
    status: PlanStatus = PlanStatus.DEFINED,
    role_bindings: frozenset[RoleBinding] | None = None,
) -> Plan:
    return Plan(
        id=uuid4(),
        name=PlanName("p"),
        practice_id=uuid4(),
        asset_ids=frozenset({uuid4()}),
        status=status,
        method_id=uuid4(),
        role_bindings=role_bindings if role_bindings is not None else frozenset(),
    )


@pytest.mark.unit
@given(role_name=_VALID_ROLE_NAME, now=_ANY_DATETIME)
def test_state_none_always_raises_plan_not_found(role_name: str, now: datetime) -> None:
    assume(role_name == role_name.strip())
    with pytest.raises(PlanNotFoundError):
        unbind_plan_role.decide(
            state=None,
            command=UnbindPlanRole(
                plan_id=uuid4(),
                role_name=RoleName(role_name),
            ),
            now=now,
        )


@pytest.mark.unit
@given(
    role_name=_VALID_ROLE_NAME,
    status=_NON_DEFINED_STATUS,
    now=_ANY_DATETIME,
)
def test_non_defined_status_always_raises_cannot_mutate(
    role_name: str, status: PlanStatus, now: datetime
) -> None:
    assume(role_name == role_name.strip())
    state = _plan(status=status, role_bindings=frozenset())
    with pytest.raises(PlanCannotMutateRoleBindingsError):
        unbind_plan_role.decide(
            state=state,
            command=UnbindPlanRole(
                plan_id=state.id,
                role_name=RoleName(role_name),
            ),
            now=now,
        )


@pytest.mark.unit
@given(
    role_name=_VALID_ROLE_NAME,
    other_name=_VALID_ROLE_NAME,
    now=_ANY_DATETIME,
)
def test_unknown_role_name_always_raises_not_bound(
    role_name: str, other_name: str, now: datetime
) -> None:
    assume(role_name == role_name.strip())
    assume(other_name == other_name.strip())
    assume(role_name != other_name)
    state = _plan(
        role_bindings=frozenset({RoleBinding(role_name=RoleName(other_name), asset_id=uuid4())}),
    )
    with pytest.raises(PlanRoleNotBoundError):
        unbind_plan_role.decide(
            state=state,
            command=UnbindPlanRole(
                plan_id=state.id,
                role_name=RoleName(role_name),
            ),
            now=now,
        )


@pytest.mark.unit
@given(role_name=_VALID_ROLE_NAME, now=_ANY_DATETIME)
def test_happy_path_emits_single_event(role_name: str, now: datetime) -> None:
    assume(role_name == role_name.strip())
    state = _plan(
        role_bindings=frozenset({RoleBinding(role_name=RoleName(role_name), asset_id=uuid4())}),
    )
    events = unbind_plan_role.decide(
        state=state,
        command=UnbindPlanRole(
            plan_id=state.id,
            role_name=RoleName(role_name),
        ),
        now=now,
    )
    assert events == [
        PlanRoleUnbound(
            plan_id=state.id,
            role_name=role_name,
            occurred_at=now,
        )
    ]
