"""State-layer tests for Plan.role_bindings + RoleBinding VO + the
slice-2 error classes.
"""

from typing import Any
from uuid import uuid4

import pytest

from cora.recipe.aggregates.method import RoleName
from cora.recipe.aggregates.plan import (
    Plan,
    PlanName,
    RoleBinding,
)


@pytest.mark.unit
def test_role_binding_is_frozen() -> None:
    b = RoleBinding(role_name=RoleName("detector"), asset_id=uuid4())
    with pytest.raises(AttributeError):
        b.role_name = RoleName("other")  # type: ignore[misc]


@pytest.mark.unit
def test_role_binding_equality_is_tuple_based() -> None:
    rid = uuid4()
    aid = uuid4()
    a = RoleBinding(role_name=RoleName("detector"), asset_id=aid)
    b = RoleBinding(role_name=RoleName("detector"), asset_id=aid)
    c = RoleBinding(role_name=RoleName("detector"), asset_id=uuid4())
    assert a == b
    assert a != c
    assert {a, b} == {a}
    _ = rid


@pytest.mark.unit
def test_plan_role_bindings_defaults_to_empty_frozenset() -> None:
    p = Plan(
        id=uuid4(),
        name=PlanName("p"),
        practice_id=uuid4(),
        asset_ids=frozenset({uuid4()}),
    )
    assert p.role_bindings == frozenset()


@pytest.mark.unit
def test_plan_content_subset_includes_empty_role_bindings() -> None:
    p = Plan(
        id=uuid4(),
        name=PlanName("p"),
        practice_id=uuid4(),
        asset_ids=frozenset({uuid4()}),
    )
    subset = p.content_subset()
    assert "role_bindings" in subset
    assert subset["role_bindings"] == []


@pytest.mark.unit
def test_plan_content_subset_sorts_role_bindings_by_role_name() -> None:
    aid = uuid4()
    bindings = frozenset(
        {
            RoleBinding(role_name=RoleName("sample_monitor"), asset_id=aid),
            RoleBinding(role_name=RoleName("detector"), asset_id=aid),
        }
    )
    p = Plan(
        id=uuid4(),
        name=PlanName("p"),
        practice_id=uuid4(),
        asset_ids=frozenset({aid}),
        role_bindings=bindings,
    )
    subset = p.content_subset()
    payload: list[Any] = subset["role_bindings"]  # type: ignore[assignment]
    role_names = [entry[0] for entry in payload]
    assert role_names == ["detector", "sample_monitor"]
