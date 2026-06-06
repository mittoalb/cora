"""Property-based tests for `remove_method_required_role.decide` (Recipe BC).

Complements `test_remove_method_required_role_decider.py` (example-
based) with universal claims across generated inputs.

  - For state=None and any well-formed command, MethodNotFoundError
    is raised regardless of any other input.
  - For state.status != DEFINED, MethodCannotMutateRequiredRolesError
    is raised before the role-not-found check (lifecycle guard fires
    first), even when state.required_roles is empty.
  - For state.status == DEFINED + role_name not present in
    state.required_roles, MethodRoleNameNotFoundError is raised.
  - For state.status == DEFINED + role_name present in
    state.required_roles, exactly one MethodRequiredRoleRemoved event
    is emitted with the injected role_name and now verbatim.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.recipe.aggregates.method import (
    Method,
    MethodCannotMutateRequiredRolesError,
    MethodName,
    MethodNotFoundError,
    MethodRequiredRoleRemoved,
    MethodRoleNameNotFoundError,
    MethodStatus,
    RoleName,
    RoleRequirement,
)
from cora.recipe.features import remove_method_required_role
from cora.recipe.features.remove_method_required_role import RemoveMethodRequiredRole

if TYPE_CHECKING:
    from datetime import datetime

_VALID_ROLE_NAME = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=50,
)
_NON_DEFINED_STATUS = st.sampled_from([MethodStatus.VERSIONED, MethodStatus.DEPRECATED])
_ANY_DATETIME = st.datetimes()


def _method(
    *,
    status: MethodStatus = MethodStatus.DEFINED,
    required_roles: frozenset[RoleRequirement] | None = None,
) -> Method:
    return Method(
        id=uuid4(),
        name=MethodName("Tomography"),
        status=status,
        required_roles=required_roles if required_roles is not None else frozenset(),
    )


def _role(role_name: str) -> RoleRequirement:
    return RoleRequirement(role_name=RoleName(role_name), family_id=uuid4())


@pytest.mark.unit
@given(role_name=_VALID_ROLE_NAME, now=_ANY_DATETIME)
def test_state_none_always_raises_method_not_found(role_name: str, now: datetime) -> None:
    assume(role_name == role_name.strip())
    with pytest.raises(MethodNotFoundError):
        remove_method_required_role.decide(
            state=None,
            command=RemoveMethodRequiredRole(
                method_id=uuid4(),
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
def test_non_defined_status_always_raises_cannot_mutate_required_roles(
    role_name: str, status: MethodStatus, now: datetime
) -> None:
    """Lifecycle guard fires before the role-not-found check, even
    when state.required_roles is empty."""
    assume(role_name == role_name.strip())
    state = _method(status=status, required_roles=frozenset())
    with pytest.raises(MethodCannotMutateRequiredRolesError) as exc_info:
        remove_method_required_role.decide(
            state=state,
            command=RemoveMethodRequiredRole(
                method_id=state.id,
                role_name=RoleName(role_name),
            ),
            now=now,
        )
    assert exc_info.value.current_status is status


@pytest.mark.unit
@given(
    role_name=_VALID_ROLE_NAME,
    other_name=_VALID_ROLE_NAME,
    now=_ANY_DATETIME,
)
def test_defined_status_unknown_role_name_raises_not_found(
    role_name: str, other_name: str, now: datetime
) -> None:
    assume(role_name == role_name.strip())
    assume(other_name == other_name.strip())
    assume(role_name != other_name)
    state = _method(required_roles=frozenset({_role(other_name)}))
    with pytest.raises(MethodRoleNameNotFoundError) as exc_info:
        remove_method_required_role.decide(
            state=state,
            command=RemoveMethodRequiredRole(
                method_id=state.id,
                role_name=RoleName(role_name),
            ),
            now=now,
        )
    assert exc_info.value.role_name == RoleName(role_name)


@pytest.mark.unit
@given(
    role_name=_VALID_ROLE_NAME,
    now=_ANY_DATETIME,
)
def test_defined_status_present_role_name_emits_single_event(role_name: str, now: datetime) -> None:
    assume(role_name == role_name.strip())
    state = _method(required_roles=frozenset({_role(role_name)}))
    events = remove_method_required_role.decide(
        state=state,
        command=RemoveMethodRequiredRole(
            method_id=state.id,
            role_name=RoleName(role_name),
        ),
        now=now,
    )
    assert events == [
        MethodRequiredRoleRemoved(
            method_id=state.id,
            role_name=role_name,
            occurred_at=now,
        )
    ]
