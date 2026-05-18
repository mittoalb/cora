"""Unit tests for the `version_plan` slice's pure decider.

Mirror of `test_version_practice_decider.py` /
`test_version_method_decider.py`. Multi-source guard
`Defined | Versioned -> Versioned`; only Deprecated rejected.
Same deliberate divergence from strict-not-idempotent (re-attesting
the same tag succeeds).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.recipe.aggregates.plan import (
    InvalidPlanVersionTagError,
    Plan,
    PlanCannotVersionError,
    PlanName,
    PlanNotFoundError,
    PlanStatus,
    PlanVersioned,
)
from cora.recipe.features import version_plan
from cora.recipe.features.version_plan import VersionPlan

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _plan(
    *,
    status: PlanStatus = PlanStatus.DEFINED,
    version: str | None = None,
) -> Plan:
    return Plan(
        id=uuid4(),
        name=PlanName("32-ID FlyScan"),
        practice_id=uuid4(),
        asset_ids=frozenset({uuid4()}),
        status=status,
        version=version,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [PlanStatus.DEFINED, PlanStatus.VERSIONED],
)
def test_decide_emits_plan_versioned_for_each_allowed_source_status(
    source: PlanStatus,
) -> None:
    state = _plan(status=source)
    events = version_plan.decide(
        state=state,
        command=VersionPlan(plan_id=state.id, version_tag="v2"),
        now=_NOW,
    )
    assert events == [PlanVersioned(plan_id=state.id, version_tag="v2", occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_trims_version_tag_via_decider() -> None:
    state = _plan()
    events = version_plan.decide(
        state=state,
        command=VersionPlan(plan_id=state.id, version_tag="  v2  "),
        now=_NOW,
    )
    assert events[0].version_tag == "v2"


@pytest.mark.unit
def test_decide_raises_plan_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(PlanNotFoundError) as exc_info:
        version_plan.decide(
            state=None,
            command=VersionPlan(plan_id=target_id, version_tag="v2"),
            now=_NOW,
        )
    assert exc_info.value.plan_id == target_id


@pytest.mark.unit
def test_decide_raises_invalid_version_tag_for_empty_string() -> None:
    state = _plan()
    with pytest.raises(InvalidPlanVersionTagError):
        version_plan.decide(
            state=state,
            command=VersionPlan(plan_id=state.id, version_tag=""),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_invalid_version_tag_for_whitespace_only() -> None:
    state = _plan()
    with pytest.raises(InvalidPlanVersionTagError):
        version_plan.decide(
            state=state,
            command=VersionPlan(plan_id=state.id, version_tag="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_invalid_version_tag_for_too_long() -> None:
    state = _plan()
    with pytest.raises(InvalidPlanVersionTagError):
        version_plan.decide(
            state=state,
            command=VersionPlan(plan_id=state.id, version_tag="v" * 51),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_cannot_version_for_deprecated_status() -> None:
    state = _plan(status=PlanStatus.DEPRECATED, version="v1")
    with pytest.raises(PlanCannotVersionError) as exc_info:
        version_plan.decide(
            state=state,
            command=VersionPlan(plan_id=state.id, version_tag="v2"),
            now=_NOW,
        )
    assert exc_info.value.plan_id == state.id
    assert exc_info.value.current_status is PlanStatus.DEPRECATED


@pytest.mark.unit
def test_decide_error_message_lists_both_allowed_source_statuses() -> None:
    state = _plan(status=PlanStatus.DEPRECATED)
    with pytest.raises(PlanCannotVersionError) as exc_info:
        version_plan.decide(
            state=state,
            command=VersionPlan(plan_id=state.id, version_tag="v2"),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Deprecated" in msg
    assert "Defined" in msg
    assert "Versioned" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _plan()
    command = VersionPlan(plan_id=state.id, version_tag="v2")
    first = version_plan.decide(state=state, command=command, now=_NOW)
    second = version_plan.decide(state=state, command=command, now=_NOW)
    assert first == second


@pytest.mark.unit
def test_decide_allows_versioning_with_same_tag_for_re_attestation() -> None:
    """Mirrors the deliberate divergence pinned for version_practice
    (Recipe 6d-2), version_method (Recipe 6b), version_family
    (Equipment 5f-2): re-attesting the same tag succeeds. Re-
    attestation is a legitimate audit moment."""
    state = _plan(status=PlanStatus.VERSIONED, version="v2")
    events = version_plan.decide(
        state=state,
        command=VersionPlan(plan_id=state.id, version_tag="v2"),
        now=_NOW,
    )
    assert events == [PlanVersioned(plan_id=state.id, version_tag="v2", occurred_at=_NOW)]
