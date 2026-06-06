"""State-layer tests for Method.required_roles, RoleRequirement,
PortRequirement, and RoleName VOs (slice 1 of the positional role-
tagging workstream; IEC 81346 Function aspect).
"""

from typing import Any
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import PortDirection
from cora.recipe.aggregates.method import (
    InvalidPortRequirementError,
    InvalidRoleNameError,
    Method,
    MethodName,
    PortRequirement,
    RoleName,
    RoleRequirement,
)

# ---------- RoleName VO ----------


@pytest.mark.unit
def test_role_name_accepts_normal_string() -> None:
    name = RoleName("detector")
    assert name.value == "detector"


@pytest.mark.unit
def test_role_name_trims_whitespace() -> None:
    name = RoleName("  sample_monitor  ")
    assert name.value == "sample_monitor"


@pytest.mark.unit
def test_role_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidRoleNameError):
        RoleName("")


@pytest.mark.unit
def test_role_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidRoleNameError):
        RoleName("   \t\n   ")


@pytest.mark.unit
def test_role_name_rejects_too_long() -> None:
    with pytest.raises(InvalidRoleNameError):
        RoleName("a" * 51)


@pytest.mark.unit
def test_role_name_accepts_max_length() -> None:
    name = RoleName("a" * 50)
    assert len(name.value) == 50


@pytest.mark.unit
def test_role_name_is_frozen() -> None:
    name = RoleName("detector")
    with pytest.raises(AttributeError):
        name.value = "other"  # type: ignore[misc]


@pytest.mark.unit
def test_role_name_equality_is_value_based() -> None:
    assert RoleName("detector") == RoleName("detector")
    assert RoleName("detector") != RoleName("sample_monitor")


# ---------- PortRequirement VO ----------


@pytest.mark.unit
def test_port_requirement_accepts_normal_tuple() -> None:
    port = PortRequirement(
        port_name="trigger_in",
        direction=PortDirection.INPUT,
        signal_type="TTL",
    )
    assert port.port_name == "trigger_in"
    assert port.direction is PortDirection.INPUT
    assert port.signal_type == "TTL"


@pytest.mark.unit
def test_port_requirement_trims_strings() -> None:
    port = PortRequirement(
        port_name="  encoder_a  ",
        direction=PortDirection.OUTPUT,
        signal_type="  Encoder  ",
    )
    assert port.port_name == "encoder_a"
    assert port.signal_type == "Encoder"


@pytest.mark.unit
def test_port_requirement_rejects_empty_port_name() -> None:
    with pytest.raises(InvalidPortRequirementError):
        PortRequirement(port_name="", direction=PortDirection.INPUT, signal_type="TTL")


@pytest.mark.unit
def test_port_requirement_rejects_whitespace_only_port_name() -> None:
    with pytest.raises(InvalidPortRequirementError):
        PortRequirement(
            port_name="   \t   ",
            direction=PortDirection.INPUT,
            signal_type="TTL",
        )


@pytest.mark.unit
def test_port_requirement_rejects_too_long_port_name() -> None:
    with pytest.raises(InvalidPortRequirementError):
        PortRequirement(
            port_name="a" * 101,
            direction=PortDirection.INPUT,
            signal_type="TTL",
        )


@pytest.mark.unit
def test_port_requirement_rejects_empty_signal_type() -> None:
    with pytest.raises(InvalidPortRequirementError):
        PortRequirement(
            port_name="trigger_in",
            direction=PortDirection.INPUT,
            signal_type="",
        )


@pytest.mark.unit
def test_port_requirement_rejects_too_long_signal_type() -> None:
    with pytest.raises(InvalidPortRequirementError):
        PortRequirement(
            port_name="trigger_in",
            direction=PortDirection.INPUT,
            signal_type="a" * 51,
        )


@pytest.mark.unit
def test_port_requirement_is_frozen() -> None:
    port = PortRequirement(
        port_name="trigger_in",
        direction=PortDirection.INPUT,
        signal_type="TTL",
    )
    with pytest.raises(AttributeError):
        port.port_name = "other"  # type: ignore[misc]


@pytest.mark.unit
def test_port_requirement_equality_is_tuple_based() -> None:
    a = PortRequirement("trigger_in", PortDirection.INPUT, "TTL")
    b = PortRequirement("trigger_in", PortDirection.INPUT, "TTL")
    c = PortRequirement("trigger_in", PortDirection.OUTPUT, "TTL")
    assert a == b
    assert a != c
    # Hashability check for frozenset membership.
    assert {a, b} == {a}


# ---------- RoleRequirement VO ----------


@pytest.mark.unit
def test_role_requirement_default_ports_empty_and_not_optional() -> None:
    family_id = uuid4()
    req = RoleRequirement(role_name=RoleName("detector"), family_id=family_id)
    assert req.required_ports == frozenset()
    assert req.optional is False


@pytest.mark.unit
def test_role_requirement_accepts_ports_and_optional_flag() -> None:
    family_id = uuid4()
    ports = frozenset(
        {PortRequirement("trigger_in", PortDirection.INPUT, "TTL")},
    )
    req = RoleRequirement(
        role_name=RoleName("detector"),
        family_id=family_id,
        required_ports=ports,
        optional=True,
    )
    assert req.required_ports == ports
    assert req.optional is True


@pytest.mark.unit
def test_role_requirement_is_frozen() -> None:
    req = RoleRequirement(role_name=RoleName("detector"), family_id=uuid4())
    with pytest.raises(AttributeError):
        req.optional = True  # type: ignore[misc]


@pytest.mark.unit
def test_role_requirement_in_frozenset_dedups_identical_content() -> None:
    family_id = uuid4()
    a = RoleRequirement(
        role_name=RoleName("detector"),
        family_id=family_id,
        required_ports=frozenset(
            {PortRequirement("trigger_in", PortDirection.INPUT, "TTL")},
        ),
    )
    b = RoleRequirement(
        role_name=RoleName("detector"),
        family_id=family_id,
        required_ports=frozenset(
            {PortRequirement("trigger_in", PortDirection.INPUT, "TTL")},
        ),
    )
    # Identical content -> identical hash -> frozenset deduplicates.
    assert frozenset({a, b}) == frozenset({a})


# ---------- Method.required_roles default + content_subset ----------


@pytest.mark.unit
def test_method_required_roles_defaults_to_empty_frozenset() -> None:
    m = Method(id=uuid4(), name=MethodName("Tomography"))
    assert m.required_roles == frozenset()


@pytest.mark.unit
def test_method_content_subset_includes_empty_required_roles() -> None:
    m = Method(id=uuid4(), name=MethodName("Tomography"))
    subset = m.content_subset()
    assert "required_roles" in subset
    assert subset["required_roles"] == []


@pytest.mark.unit
def test_method_content_subset_sorts_roles_by_role_name() -> None:
    family_id = uuid4()
    roles = frozenset(
        {
            RoleRequirement(role_name=RoleName("sample_monitor"), family_id=family_id),
            RoleRequirement(role_name=RoleName("detector"), family_id=family_id),
        }
    )
    m = Method(
        id=uuid4(),
        name=MethodName("DualImagingTomography"),
        required_roles=roles,
    )
    subset = m.content_subset()
    role_names = [r["role_name"] for r in subset["required_roles"]]  # type: ignore[index]
    assert role_names == ["detector", "sample_monitor"]


@pytest.mark.unit
def test_method_content_subset_serializes_role_payload_shape() -> None:
    family_id = uuid4()
    role = RoleRequirement(
        role_name=RoleName("detector"),
        family_id=family_id,
        required_ports=frozenset(
            {
                PortRequirement("trigger_in", PortDirection.INPUT, "TTL"),
                PortRequirement("data_out", PortDirection.OUTPUT, "Network"),
            }
        ),
        optional=False,
    )
    m = Method(
        id=uuid4(),
        name=MethodName("Tomography"),
        required_roles=frozenset({role}),
    )
    subset = m.content_subset()
    required_roles_payload: list[dict[str, Any]] = subset["required_roles"]  # type: ignore[assignment]
    payload = required_roles_payload[0]
    assert payload["role_name"] == "detector"
    assert payload["family_id"] == str(family_id)
    assert payload["optional"] is False
    # required_ports sorted by (port_name, direction).
    ports: list[dict[str, str]] = payload["required_ports"]
    assert [p["port_name"] for p in ports] == [
        "data_out",
        "trigger_in",
    ]
