"""Unit tests for the `add_method_required_role` slice's pure decider.

The decider:
  - Raises MethodNotFoundError on empty state.
  - Raises MethodCannotMutateRequiredRolesError on Versioned/Deprecated
    status (lifecycle guard restricts to Defined).
  - Raises MethodRoleNameAlreadyDeclaredError on duplicate role_name
    (strict-not-idempotent on the role_name identity).
  - Emits MethodRequiredRoleAdded otherwise.

Mirror tests live in `test_remove_method_required_role_decider.py`.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import PortDirection
from cora.recipe.aggregates.method import (
    Method,
    MethodCannotMutateRequiredRolesError,
    MethodName,
    MethodNotFoundError,
    MethodRequiredRoleAdded,
    MethodRoleNameAlreadyDeclaredError,
    MethodStatus,
    PortRequirement,
    RoleName,
    RoleRequirement,
)
from cora.recipe.features import add_method_required_role
from cora.recipe.features.add_method_required_role import AddMethodRequiredRole

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


def _requirement(role_name: str = "detector") -> RoleRequirement:
    return RoleRequirement(
        role_name=RoleName(role_name),
        family_id=uuid4(),
        required_ports=frozenset(
            {PortRequirement("trigger_in", PortDirection.INPUT, "TTL")},
        ),
        optional=False,
    )


@pytest.mark.unit
def test_decide_raises_when_state_is_none() -> None:
    method_id = uuid4()
    with pytest.raises(MethodNotFoundError):
        add_method_required_role.decide(
            state=None,
            command=AddMethodRequiredRole(
                method_id=method_id,
                requirement=_requirement(),
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_emits_event_on_first_role_added() -> None:
    state = _method()
    req = _requirement()
    events = add_method_required_role.decide(
        state=state,
        command=AddMethodRequiredRole(method_id=state.id, requirement=req),
        now=_NOW,
    )
    assert len(events) == 1
    evt = events[0]
    assert isinstance(evt, MethodRequiredRoleAdded)
    assert evt.method_id == state.id
    assert evt.role_name == "detector"
    assert evt.family_id == req.family_id
    assert evt.optional is False
    assert evt.occurred_at == _NOW
    assert tuple(evt.required_ports) == (
        {
            "port_name": "trigger_in",
            "direction": "Input",
            "signal_type": "TTL",
        },
    )


@pytest.mark.unit
def test_decide_accepts_empty_required_ports() -> None:
    state = _method()
    pure_binding = RoleRequirement(
        role_name=RoleName("axis"),
        family_id=uuid4(),
    )
    events = add_method_required_role.decide(
        state=state,
        command=AddMethodRequiredRole(method_id=state.id, requirement=pure_binding),
        now=_NOW,
    )
    assert events[0].required_ports == ()


@pytest.mark.unit
def test_decide_emits_event_for_second_distinct_role_name() -> None:
    existing = _requirement("detector")
    state = _method(required_roles=frozenset({existing}))
    new_role = _requirement("sample_monitor")
    events = add_method_required_role.decide(
        state=state,
        command=AddMethodRequiredRole(method_id=state.id, requirement=new_role),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].role_name == "sample_monitor"


@pytest.mark.unit
def test_decide_rejects_duplicate_role_name_strict_not_idempotent() -> None:
    existing = _requirement("detector")
    state = _method(required_roles=frozenset({existing}))
    new_role = _requirement("detector")  # same name, different family_id
    with pytest.raises(MethodRoleNameAlreadyDeclaredError) as exc_info:
        add_method_required_role.decide(
            state=state,
            command=AddMethodRequiredRole(method_id=state.id, requirement=new_role),
            now=_NOW,
        )
    assert exc_info.value.method_id == state.id
    assert exc_info.value.role_name == RoleName("detector")


@pytest.mark.unit
def test_decide_rejects_when_status_is_versioned() -> None:
    state = _method(status=MethodStatus.VERSIONED)
    with pytest.raises(MethodCannotMutateRequiredRolesError) as exc_info:
        add_method_required_role.decide(
            state=state,
            command=AddMethodRequiredRole(method_id=state.id, requirement=_requirement()),
            now=_NOW,
        )
    assert exc_info.value.current_status is MethodStatus.VERSIONED


@pytest.mark.unit
def test_decide_rejects_when_status_is_deprecated() -> None:
    state = _method(status=MethodStatus.DEPRECATED)
    with pytest.raises(MethodCannotMutateRequiredRolesError):
        add_method_required_role.decide(
            state=state,
            command=AddMethodRequiredRole(method_id=state.id, requirement=_requirement()),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_preserves_existing_needed_family_ids_invariant() -> None:
    """Adding a required role must not silently affect needed_family_ids.

    Slice 1 is purely additive: required_roles lands alongside the
    existing fields; the decider does not touch needed_family_ids.
    This test pins that contract at the decider boundary.
    """
    state = _method()
    add_method_required_role.decide(
        state=state,
        command=AddMethodRequiredRole(method_id=state.id, requirement=_requirement()),
        now=_NOW,
    )
    # State is frozen and unchanged by the pure decider.
    assert state.needed_family_ids == frozenset()
