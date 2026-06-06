"""Property-based tests for `add_method_required_role.decide` (Recipe BC).

Complements `test_add_method_required_role_decider.py` (example-
based) with universal claims across generated inputs.

  - For state=None and any well-formed command, MethodNotFoundError
    is raised regardless of any other input.
  - For state.status != DEFINED and any well-formed command,
    MethodCannotMutateRequiredRolesError is raised before the
    role_name-uniqueness check (lifecycle guard fires first).
  - For state.status == DEFINED + valid command + role_name not yet
    declared, exactly one MethodRequiredRoleAdded event is emitted
    with the injected fields verbatim.
  - For any role already in state.required_roles,
    MethodRoleNameAlreadyDeclaredError is raised regardless of
    family_id / required_ports / optional differences (uniqueness
    keyed on role_name).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

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

if TYPE_CHECKING:
    from datetime import datetime

# Role names: printable ASCII excluding leading/trailing whitespace, 1-50 chars.
_VALID_ROLE_NAME = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=50,
)
_PORT_NAME = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=100,
)
_SIGNAL_TYPE = st.text(
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


def _requirement(
    role_name: str,
    *,
    optional: bool = False,
    port: PortRequirement | None = None,
) -> RoleRequirement:
    return RoleRequirement(
        role_name=RoleName(role_name),
        family_id=uuid4(),
        required_ports=frozenset({port}) if port is not None else frozenset(),
        optional=optional,
    )


@pytest.mark.unit
@given(role_name=_VALID_ROLE_NAME, now=_ANY_DATETIME)
def test_state_none_always_raises_method_not_found(role_name: str, now: datetime) -> None:
    assume(role_name == role_name.strip())
    with pytest.raises(MethodNotFoundError):
        add_method_required_role.decide(
            state=None,
            command=AddMethodRequiredRole(
                method_id=uuid4(),
                requirement=_requirement(role_name),
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
    """Lifecycle guard fires before the role-uniqueness check; any
    non-Defined status rejects regardless of role_name novelty."""
    assume(role_name == role_name.strip())
    state = _method(status=status)
    with pytest.raises(MethodCannotMutateRequiredRolesError) as exc_info:
        add_method_required_role.decide(
            state=state,
            command=AddMethodRequiredRole(
                method_id=state.id,
                requirement=_requirement(role_name),
            ),
            now=now,
        )
    assert exc_info.value.current_status is status


@pytest.mark.unit
@given(
    role_name=_VALID_ROLE_NAME,
    port_name=_PORT_NAME,
    signal_type=_SIGNAL_TYPE,
    direction=st.sampled_from(list(PortDirection)),
    optional=st.booleans(),
    now=_ANY_DATETIME,
)
def test_defined_status_emits_single_event_with_injected_fields(
    role_name: str,
    port_name: str,
    signal_type: str,
    direction: PortDirection,
    optional: bool,
    now: datetime,
) -> None:
    assume(role_name == role_name.strip())
    assume(port_name == port_name.strip())
    assume(signal_type == signal_type.strip())
    state = _method()
    port = PortRequirement(
        port_name=port_name,
        direction=direction,
        signal_type=signal_type,
    )
    req = _requirement(role_name, optional=optional, port=port)
    events = add_method_required_role.decide(
        state=state,
        command=AddMethodRequiredRole(method_id=state.id, requirement=req),
        now=now,
    )
    assert len(events) == 1
    evt = events[0]
    assert isinstance(evt, MethodRequiredRoleAdded)
    assert evt.method_id == state.id
    assert evt.role_name == role_name
    assert evt.family_id == req.family_id
    assert evt.optional is optional
    assert evt.occurred_at == now
    assert evt.required_ports == (
        {
            "port_name": port_name,
            "direction": direction.value,
            "signal_type": signal_type,
        },
    )


@pytest.mark.unit
@given(
    role_name=_VALID_ROLE_NAME,
    now=_ANY_DATETIME,
)
def test_duplicate_role_name_always_raises_already_declared(role_name: str, now: datetime) -> None:
    """If a role_name is already in state.required_roles, any
    subsequent add of the same role_name raises, even with a
    different family_id, different required_ports, or different
    optional flag. Uniqueness is keyed on role_name alone."""
    assume(role_name == role_name.strip())
    existing = _requirement(role_name)
    state = _method(required_roles=frozenset({existing}))
    # Try to add a "different" role with the same name: different
    # family, different ports, opposite optional flag.
    different = RoleRequirement(
        role_name=RoleName(role_name),
        family_id=uuid4(),
        required_ports=frozenset(
            {PortRequirement("trigger_in", PortDirection.INPUT, "TTL")},
        ),
        optional=not existing.optional,
    )
    with pytest.raises(MethodRoleNameAlreadyDeclaredError) as exc_info:
        add_method_required_role.decide(
            state=state,
            command=AddMethodRequiredRole(method_id=state.id, requirement=different),
            now=now,
        )
    assert exc_info.value.role_name == RoleName(role_name)
