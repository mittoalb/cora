"""Unit tests for the Plan aggregate's evolver."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.recipe.aggregates.plan import (
    Plan,
    PlanName,
    PlanStatus,
    evolve,
    fold,
)
from cora.recipe.aggregates.plan.events import (
    PlanDefined,
    PlanDeprecated,
    PlanVersioned,
)

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _plan_defined(
    *,
    plan_id: UUID | None = None,
    practice_id: UUID | None = None,
    asset_ids: list[UUID] | None = None,
) -> PlanDefined:
    """Test helper: PlanDefined with sensible defaults for non-relevant fields."""
    return PlanDefined(
        plan_id=plan_id or uuid4(),
        name="32-ID FlyScan",
        practice_id=practice_id or uuid4(),
        asset_ids=asset_ids if asset_ids is not None else [uuid4()],
        method_id=uuid4(),
        method_needs_capabilities_snapshot=[uuid4()],
        asset_capabilities_snapshot={},
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_evolve_plan_defined_sets_status_to_defined() -> None:
    """PlanDefined is the genesis event; status defaults to Defined
    via the evolver. Audit snapshots in payload are NOT folded into
    state (gate-review Q4: slim aggregate)."""
    plan_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    state = evolve(
        None,
        PlanDefined(
            plan_id=plan_id,
            name="32-ID FlyScan",
            practice_id=practice_id,
            asset_ids=[asset_id],
            method_id=uuid4(),
            method_needs_capabilities_snapshot=[uuid4()],
            asset_capabilities_snapshot={asset_id: [uuid4()]},
            occurred_at=_NOW,
        ),
    )
    assert state == Plan(
        id=plan_id,
        name=PlanName("32-ID FlyScan"),
        practice_id=practice_id,
        asset_ids=frozenset({asset_id}),
        status=PlanStatus.DEFINED,
    )


@pytest.mark.unit
def test_evolve_plan_defined_converts_asset_ids_list_to_frozenset() -> None:
    """Event payload carries `list[UUID]` (JSON-friendly); state
    holds `frozenset[UUID]` (set semantics for membership). Same
    precedent as Method's needs_capabilities."""
    a1 = uuid4()
    a2 = uuid4()
    state = evolve(None, _plan_defined(asset_ids=[a1, a2, a1]))  # duplicate
    assert state.asset_ids == frozenset({a1, a2})
    assert isinstance(state.asset_ids, frozenset)


@pytest.mark.unit
def test_evolve_plan_defined_does_not_fold_audit_snapshots() -> None:
    """Slim aggregate: snapshots in payload are NOT folded into
    state. Plan state has no method_id, method_needs_capabilities,
    or asset_capabilities fields. This test pins that future
    additions don't accidentally widen state."""
    state = evolve(None, _plan_defined())
    # Plan dataclass field set is the contract.
    assert {f for f in state.__dataclass_fields__} == {
        "id",
        "name",
        "practice_id",
        "asset_ids",
        "status",
        "version",
    }


@pytest.mark.unit
def test_evolve_plan_defined_starts_with_null_version() -> None:
    """Genesis-only stream folds with version=None (additive-state
    pattern; pre-6e-2 streams fold cleanly without an upcaster)."""
    state = evolve(None, _plan_defined())
    assert state.version is None


# ---------- PlanVersioned (Phase 6e-2) ----------


@pytest.mark.unit
def test_evolve_plan_versioned_flips_status_and_sets_version() -> None:
    plan_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    defined = Plan(
        id=plan_id,
        name=PlanName("32-ID FlyScan"),
        practice_id=practice_id,
        asset_ids=frozenset({asset_id}),
        status=PlanStatus.DEFINED,
    )
    versioned = evolve(
        defined,
        PlanVersioned(plan_id=plan_id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned.status is PlanStatus.VERSIONED
    assert versioned.version == "v2"
    # Other state preserved.
    assert versioned.id == plan_id
    assert versioned.practice_id == practice_id
    assert versioned.asset_ids == frozenset({asset_id})


@pytest.mark.unit
def test_evolve_plan_versioned_replaces_prior_version_tag() -> None:
    """Subsequent revisions overwrite version with the new label."""
    plan_id = uuid4()
    versioned_v1 = Plan(
        id=plan_id,
        name=PlanName("X"),
        practice_id=uuid4(),
        asset_ids=frozenset({uuid4()}),
        status=PlanStatus.VERSIONED,
        version="v1",
    )
    versioned_v2 = evolve(
        versioned_v1,
        PlanVersioned(plan_id=plan_id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned_v2.version == "v2"


@pytest.mark.unit
def test_evolve_plan_versioned_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, PlanVersioned(plan_id=uuid4(), version_tag="v1", occurred_at=_NOW))


@pytest.mark.unit
def test_evolve_plan_versioned_preserves_practice_id_and_asset_ids() -> None:
    """Critical invariant: cross-aggregate refs MUST carry through
    the version transition. Same safety-net pattern as Practice's
    evolver preserve tests."""
    practice_id = uuid4()
    a1 = uuid4()
    a2 = uuid4()
    defined = Plan(
        id=uuid4(),
        name=PlanName("X"),
        practice_id=practice_id,
        asset_ids=frozenset({a1, a2}),
        status=PlanStatus.DEFINED,
    )
    versioned = evolve(
        defined,
        PlanVersioned(plan_id=defined.id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned.practice_id == practice_id
    assert versioned.asset_ids == frozenset({a1, a2})


# ---------- PlanDeprecated (Phase 6e-2) ----------


@pytest.mark.unit
def test_evolve_plan_deprecated_flips_status_and_preserves_version() -> None:
    """version preserved across deprecation. Mirrors Practice/Method/
    Capability shape — audit signal of the last revision before
    deprecation stays visible on the Deprecated state."""
    plan_id = uuid4()
    practice_id = uuid4()
    asset_id = uuid4()
    versioned = Plan(
        id=plan_id,
        name=PlanName("X"),
        practice_id=practice_id,
        asset_ids=frozenset({asset_id}),
        status=PlanStatus.VERSIONED,
        version="v3",
    )
    deprecated = evolve(
        versioned,
        PlanDeprecated(plan_id=plan_id, occurred_at=_NOW),
    )
    assert deprecated.status is PlanStatus.DEPRECATED
    assert deprecated.version == "v3"
    # Cross-aggregate refs preserved across deprecation too.
    assert deprecated.practice_id == practice_id
    assert deprecated.asset_ids == frozenset({asset_id})


@pytest.mark.unit
def test_evolve_plan_deprecated_from_defined_preserves_null_version() -> None:
    defined = Plan(
        id=uuid4(),
        name=PlanName("X"),
        practice_id=uuid4(),
        asset_ids=frozenset({uuid4()}),
        status=PlanStatus.DEFINED,
    )
    deprecated = evolve(defined, PlanDeprecated(plan_id=defined.id, occurred_at=_NOW))
    assert deprecated.status is PlanStatus.DEPRECATED
    assert deprecated.version is None


@pytest.mark.unit
def test_evolve_plan_deprecated_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, PlanDeprecated(plan_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_fold_define_version_yields_versioned_plan() -> None:
    plan_id = uuid4()
    state = fold(
        [
            _plan_defined(plan_id=plan_id),
            PlanVersioned(plan_id=plan_id, version_tag="v2", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is PlanStatus.VERSIONED
    assert state.version == "v2"


@pytest.mark.unit
def test_fold_define_version_version_yields_latest_version_tag() -> None:
    """Multi-revision fold: latest version_tag wins."""
    plan_id = uuid4()
    state = fold(
        [
            _plan_defined(plan_id=plan_id),
            PlanVersioned(plan_id=plan_id, version_tag="v1", occurred_at=_NOW),
            PlanVersioned(plan_id=plan_id, version_tag="v2", occurred_at=_NOW),
            PlanVersioned(plan_id=plan_id, version_tag="v3", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.version == "v3"


@pytest.mark.unit
def test_fold_define_version_deprecate_preserves_version_through_deprecation() -> None:
    """Full lifecycle audit: define → version → deprecate keeps the
    last version_tag as a historical record on the deprecated state."""
    plan_id = uuid4()
    state = fold(
        [
            _plan_defined(plan_id=plan_id),
            PlanVersioned(plan_id=plan_id, version_tag="v2", occurred_at=_NOW),
            PlanDeprecated(plan_id=plan_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is PlanStatus.DEPRECATED
    assert state.version == "v2"


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_plan_defined_returns_plan() -> None:
    plan_id = uuid4()
    state = fold([_plan_defined(plan_id=plan_id)])
    assert state is not None
    assert state.id == plan_id
    assert state.status is PlanStatus.DEFINED


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    events = [_plan_defined()]
    assert fold(events) == fold(events)
