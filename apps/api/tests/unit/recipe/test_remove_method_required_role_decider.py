"""Unit tests for the `remove_method_required_role` slice's pure decider.

The decider:
  - Raises MethodNotFoundError on empty state.
  - Raises MethodCannotMutateRequiredRolesError on Versioned/Deprecated
    status (symmetric with add).
  - Raises MethodRoleNameNotFoundError on unknown role_name (strict-
    not-idempotent).
  - Emits MethodRequiredRoleRemoved otherwise.

Mirror of `test_add_method_required_role_decider.py`.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

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

_NOW = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)


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


def _role(name: str = "detector") -> RoleRequirement:
    return RoleRequirement(role_name=RoleName(name), family_id=uuid4())


@pytest.mark.unit
def test_decide_raises_when_state_is_none() -> None:
    method_id = uuid4()
    with pytest.raises(MethodNotFoundError):
        remove_method_required_role.decide(
            state=None,
            command=RemoveMethodRequiredRole(
                method_id=method_id,
                role_name=RoleName("detector"),
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_emits_event_when_role_present() -> None:
    role = _role("detector")
    state = _method(required_roles=frozenset({role}))
    events = remove_method_required_role.decide(
        state=state,
        command=RemoveMethodRequiredRole(
            method_id=state.id,
            role_name=RoleName("detector"),
        ),
        now=_NOW,
    )
    assert events == [
        MethodRequiredRoleRemoved(
            method_id=state.id,
            role_name="detector",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_rejects_unknown_role_name_strict_not_idempotent() -> None:
    state = _method(required_roles=frozenset({_role("detector")}))
    with pytest.raises(MethodRoleNameNotFoundError) as exc_info:
        remove_method_required_role.decide(
            state=state,
            command=RemoveMethodRequiredRole(
                method_id=state.id,
                role_name=RoleName("sample_monitor"),
            ),
            now=_NOW,
        )
    assert exc_info.value.method_id == state.id
    assert exc_info.value.role_name == RoleName("sample_monitor")


@pytest.mark.unit
def test_decide_rejects_when_status_is_versioned() -> None:
    role = _role("detector")
    state = _method(status=MethodStatus.VERSIONED, required_roles=frozenset({role}))
    with pytest.raises(MethodCannotMutateRequiredRolesError) as exc_info:
        remove_method_required_role.decide(
            state=state,
            command=RemoveMethodRequiredRole(
                method_id=state.id,
                role_name=RoleName("detector"),
            ),
            now=_NOW,
        )
    assert exc_info.value.current_status is MethodStatus.VERSIONED


@pytest.mark.unit
def test_decide_rejects_when_status_is_deprecated() -> None:
    role = _role("detector")
    state = _method(status=MethodStatus.DEPRECATED, required_roles=frozenset({role}))
    with pytest.raises(MethodCannotMutateRequiredRolesError):
        remove_method_required_role.decide(
            state=state,
            command=RemoveMethodRequiredRole(
                method_id=state.id,
                role_name=RoleName("detector"),
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_lifecycle_guard_fires_before_unknown_role_guard() -> None:
    """Versioned Method with no roles still surfaces the lifecycle
    guard rather than a not-found-on-empty-set guard. This pins
    the decider's guard ordering: lifecycle first, then identity.
    """
    state = _method(status=MethodStatus.VERSIONED, required_roles=frozenset())
    with pytest.raises(MethodCannotMutateRequiredRolesError):
        remove_method_required_role.decide(
            state=state,
            command=RemoveMethodRequiredRole(
                method_id=state.id,
                role_name=RoleName("detector"),
            ),
            now=_NOW,
        )
