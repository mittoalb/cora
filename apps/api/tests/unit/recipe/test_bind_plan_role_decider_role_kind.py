"""Layer 3 sub-slice 3D: decider tests for the role_kind path of `bind_plan_role`.

Pins the ANY-single-family disjunction per Lock 17:
  - Asset.family_ids walked via context.family_lookups
  - bound iff AT LEAST ONE Family advertises role_kind in
    presents_as AND has affordances superset of
    role_lookup_result.required_affordances
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import Asset, AssetName
from cora.infrastructure.ports import FamilyLookupResult, RoleLookupResult
from cora.recipe.aggregates.method import (
    Method,
    MethodName,
    RoleName,
    RoleRequirement,
)
from cora.recipe.aggregates.plan import (
    AssetDoesNotPresentRequiredRoleError,
    Plan,
    PlanName,
    PlanRoleBound,
    PlanRoleFamilyNotResolvableError,
    PlanStatus,
    RoleBinding,
    Wire,
)
from cora.recipe.features import bind_plan_role
from cora.recipe.features.bind_plan_role import BindPlanRole, BindPlanRoleContext

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def _plan(
    *,
    asset_id: UUID,
    method_id: UUID,
) -> Plan:
    return Plan(
        id=uuid4(),
        name=PlanName("p"),
        practice_id=uuid4(),
        asset_ids=frozenset({asset_id}),
        status=PlanStatus.DEFINED,
        method_id=method_id,
        role_bindings=frozenset[RoleBinding](),
        wires=frozenset[Wire](),
    )


def _method(method_id: UUID, *, role_name: str, role_kind: UUID) -> Method:
    return Method(
        id=method_id,
        name=MethodName("m"),
        required_roles=frozenset(
            {RoleRequirement(role_name=RoleName(role_name), role_kind=role_kind)}
        ),
    )


def _asset(asset_id: UUID, *, family_ids: frozenset[UUID]) -> Asset:
    from cora.equipment.aggregates.asset import AssetLevel

    return Asset(
        id=asset_id,
        name=AssetName("a"),
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        family_ids=family_ids,
        ports=frozenset(),
    )


def _role_lookup(role_id: UUID, *, required: frozenset[str]) -> RoleLookupResult:
    return RoleLookupResult(
        id=role_id,
        name="X",
        required_affordances=required,
        optional_affordances=frozenset(),
    )


def _family_lookup(
    family_id: UUID, *, presents_as: frozenset[UUID], affordances: frozenset[str]
) -> FamilyLookupResult:
    return FamilyLookupResult(
        id=family_id,
        name="X",
        status="Defined",
        affordances=affordances,
        presents_as=presents_as,
    )


@pytest.mark.unit
def test_decide_role_kind_path_succeeds_when_single_family_satisfies() -> None:
    """ANY-single-family disjunction: only one Family on the Asset needs
    to advertise the Role AND cover its required_affordances."""
    aid = uuid4()
    mid = uuid4()
    fid = uuid4()
    rid = uuid4()
    state = _plan(asset_id=aid, method_id=mid)
    method = _method(mid, role_name="detector", role_kind=rid)
    asset = _asset(aid, family_ids=frozenset({fid}))
    role_lookup = _role_lookup(rid, required=frozenset({"Imageable"}))
    family_lookups = {
        fid: _family_lookup(
            fid,
            presents_as=frozenset({rid}),
            affordances=frozenset({"Imageable"}),
        )
    }
    events = bind_plan_role.decide(
        state=state,
        command=BindPlanRole(plan_id=state.id, role_name=RoleName("detector"), asset_id=aid),
        context=BindPlanRoleContext(
            method=method,
            asset=asset,
            role_lookup_result=role_lookup,
            family_lookups=family_lookups,
        ),
        now=_NOW,
    )
    assert events == [
        PlanRoleBound(plan_id=state.id, role_name="detector", asset_id=aid, occurred_at=_NOW)
    ]


@pytest.mark.unit
def test_decide_role_kind_path_disjunction_accepts_when_one_of_many_satisfies() -> None:
    """Asset carries 3 Families; only one advertises the Role -> still satisfies."""
    aid = uuid4()
    mid = uuid4()
    fid_advertising = uuid4()
    fid_other_a = uuid4()
    fid_other_b = uuid4()
    rid = uuid4()
    state = _plan(asset_id=aid, method_id=mid)
    method = _method(mid, role_name="detector", role_kind=rid)
    asset = _asset(
        aid,
        family_ids=frozenset({fid_advertising, fid_other_a, fid_other_b}),
    )
    role_lookup = _role_lookup(rid, required=frozenset({"Imageable"}))
    family_lookups = {
        fid_advertising: _family_lookup(
            fid_advertising,
            presents_as=frozenset({rid}),
            affordances=frozenset({"Imageable"}),
        ),
        fid_other_a: _family_lookup(fid_other_a, presents_as=frozenset(), affordances=frozenset()),
        fid_other_b: _family_lookup(fid_other_b, presents_as=frozenset(), affordances=frozenset()),
    }
    events = bind_plan_role.decide(
        state=state,
        command=BindPlanRole(plan_id=state.id, role_name=RoleName("detector"), asset_id=aid),
        context=BindPlanRoleContext(
            method=method,
            asset=asset,
            role_lookup_result=role_lookup,
            family_lookups=family_lookups,
        ),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_role_kind_path_raises_when_no_family_advertises_role() -> None:
    aid = uuid4()
    mid = uuid4()
    fid = uuid4()
    rid = uuid4()
    state = _plan(asset_id=aid, method_id=mid)
    method = _method(mid, role_name="detector", role_kind=rid)
    asset = _asset(aid, family_ids=frozenset({fid}))
    role_lookup = _role_lookup(rid, required=frozenset({"Imageable"}))
    family_lookups = {
        fid: _family_lookup(
            fid,
            presents_as=frozenset(),  # Family does NOT advertise this Role
            affordances=frozenset({"Imageable"}),
        )
    }
    with pytest.raises(AssetDoesNotPresentRequiredRoleError) as exc:
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(plan_id=state.id, role_name=RoleName("detector"), asset_id=aid),
            context=BindPlanRoleContext(
                method=method,
                asset=asset,
                role_lookup_result=role_lookup,
                family_lookups=family_lookups,
            ),
            now=_NOW,
        )
    assert exc.value.role_kind == rid
    assert exc.value.asset_id == aid


@pytest.mark.unit
def test_decide_role_kind_path_raises_when_family_advertises_but_lacks_affordances() -> None:
    """Family advertises the Role but is missing a required_affordance."""
    aid = uuid4()
    mid = uuid4()
    fid = uuid4()
    rid = uuid4()
    state = _plan(asset_id=aid, method_id=mid)
    method = _method(mid, role_name="detector", role_kind=rid)
    asset = _asset(aid, family_ids=frozenset({fid}))
    role_lookup = _role_lookup(rid, required=frozenset({"Imageable", "Streamable"}))
    family_lookups = {
        fid: _family_lookup(
            fid,
            presents_as=frozenset({rid}),
            affordances=frozenset({"Imageable"}),  # missing Streamable
        )
    }
    with pytest.raises(AssetDoesNotPresentRequiredRoleError):
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(plan_id=state.id, role_name=RoleName("detector"), asset_id=aid),
            context=BindPlanRoleContext(
                method=method,
                asset=asset,
                role_lookup_result=role_lookup,
                family_lookups=family_lookups,
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_role_kind_path_raises_when_family_lookup_misses() -> None:
    """An Asset.family_ids member that doesn't resolve via FamilyLookup."""
    aid = uuid4()
    mid = uuid4()
    fid = uuid4()
    rid = uuid4()
    state = _plan(asset_id=aid, method_id=mid)
    method = _method(mid, role_name="detector", role_kind=rid)
    asset = _asset(aid, family_ids=frozenset({fid}))
    role_lookup = _role_lookup(rid, required=frozenset())
    # family_lookups dict empty -> the only family_id on the Asset is missing.
    with pytest.raises(PlanRoleFamilyNotResolvableError) as exc:
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(plan_id=state.id, role_name=RoleName("detector"), asset_id=aid),
            context=BindPlanRoleContext(
                method=method,
                asset=asset,
                role_lookup_result=role_lookup,
                family_lookups={},
            ),
            now=_NOW,
        )
    assert exc.value.missing_family_id == fid
