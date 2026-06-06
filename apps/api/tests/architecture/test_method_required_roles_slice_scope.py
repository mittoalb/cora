"""Architecture-fitness tests pinning the slice-1 scope of the
positional role-tagging workstream.

Pins what slice 1 ships and what it deliberately defers, so a
future refactor that conflates slice 1 with slice 2 (Plan-side role
bindings + Wire-role-endpoint invariant) trips a clear test name.
See [[project-method-required-roles-design]] §"Slice plan".

Also pins the cross-BC type-reuse documentation: the
`PortDirection` enum from Equipment BC is the ONLY new cross-BC
type dependency added by slice 1.
"""

import inspect
from pathlib import Path

import pytest

from cora.recipe.aggregates.method import RoleRequirement
from cora.recipe.aggregates.method import state as method_state
from cora.recipe.features import add_method_required_role, remove_method_required_role


@pytest.mark.architecture
def test_add_slice_directory_has_six_files() -> None:
    """Slice 1 ships the canonical 6-file slice topology
    (__init__, command, decider, handler, route, tool), same shape
    as add_asset_owner and update_method_parameters_schema. Catches a
    refactor that accidentally adds an extra file or drops one."""
    slice_dir = Path(add_method_required_role.__file__).parent
    py_files = sorted(p.name for p in slice_dir.glob("*.py"))
    assert py_files == [
        "__init__.py",
        "command.py",
        "decider.py",
        "handler.py",
        "route.py",
        "tool.py",
    ]


@pytest.mark.architecture
def test_remove_slice_directory_has_six_files() -> None:
    """R2 symmetry: remove slice mirrors add slice's 6-file shape."""
    slice_dir = Path(remove_method_required_role.__file__).parent
    py_files = sorted(p.name for p in slice_dir.glob("*.py"))
    assert py_files == [
        "__init__.py",
        "command.py",
        "decider.py",
        "handler.py",
        "route.py",
        "tool.py",
    ]


@pytest.mark.architecture
def test_role_requirement_carries_required_ports_field() -> None:
    """Pins that RoleRequirement carries `required_ports` (the
    structural closure the 2026-06-06 critique demanded). A future
    refactor that drops the field would silently re-introduce the
    role-table-vs-wire-graph divergence Option A was originally
    refuted on."""
    field_names = {f for f in RoleRequirement.__dataclass_fields__}
    assert "required_ports" in field_names
    assert "role_name" in field_names
    assert "family_id" in field_names
    assert "optional" in field_names


@pytest.mark.architecture
def test_method_state_reuses_port_direction_from_equipment_bc() -> None:
    """The PortDirection enum from Equipment BC is the ONLY new cross-
    BC type dependency added by slice 1. Pinned: Method state imports
    PortDirection (and the two re-exported port-length constants) and
    nothing else from equipment.aggregates.asset.

    A future addition of a new cross-BC import would surface here and
    require an explicit design review (per project_bc_map.md and
    [[project-method-required-roles-design]] §"Cross-BC impact")."""
    source = inspect.getsource(method_state)
    # Positive: PortDirection + two length constants ARE imported.
    assert "PortDirection" in source
    assert "PORT_NAME_MAX_LENGTH" in source
    assert "PORT_SIGNAL_TYPE_MAX_LENGTH" in source
    # Negative: no other cora.equipment surface leaks into state.py.
    # All cross-BC lines must be the single "from cora.equipment..."
    # block. Counting "from cora.equipment" anchors detection without
    # depending on exact whitespace formatting.
    cross_bc_lines = [
        line for line in source.splitlines() if line.strip().startswith("from cora.equipment")
    ]
    assert len(cross_bc_lines) == 1, (
        f"Expected exactly one cora.equipment import line in Method "
        f"state.py; found {len(cross_bc_lines)}: {cross_bc_lines}"
    )


@pytest.mark.architecture
def test_plan_decider_does_not_yet_reference_required_roles() -> None:
    """Slice 1 ships Method-side declaration only. Slice 2 will add
    Plan-side `role_bindings` + `PlanRolePortCoverageNotSatisfiedError`
    + `PlanWireRoleEndpointMismatchError` and is the natural home for
    Plan-decider awareness of required_roles. Until then, the Plan
    decider MUST NOT silently start enforcing role coverage, or the
    slice-1 vs slice-2 separation collapses.

    Pin so adding role-aware Plan validation requires a deliberate
    edit that also updates this test (which forces the test author to
    notice the slice-boundary shift)."""
    from cora.recipe.features.define_plan import decider as define_plan_decider

    source = inspect.getsource(define_plan_decider)
    # required_roles is a Method-state field; if the Plan decider
    # starts reading it, the slice-2 work has bled into slice 1.
    assert "required_roles" not in source, (
        "Plan define decider must not reference Method.required_roles "
        "until slice 2 ships role-aware Plan validation"
    )
