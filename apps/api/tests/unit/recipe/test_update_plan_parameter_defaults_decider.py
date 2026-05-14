"""Unit tests for the `update_plan_parameter_defaults` slice's pure decider.

Phase 6g-b. The decider:
  - Raises PlanNotFoundError on empty state
  - Merges the patch into prior parameter_defaults via RFC 7396 semantics
  - Validates the merged result against the supplied
    method_parameters_schema; STRICT when None (post-6g audit reversal:
    non-empty defaults rejected when no schema declared)
  - No-ops (returns []) on unchanged-vs-current
  - Emits PlanParameterDefaultsUpdated with the post-merge dict otherwise
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from cora.recipe.aggregates.plan import (
    InvalidPlanParameterDefaultsError,
    Plan,
    PlanName,
    PlanNotFoundError,
    PlanParameterDefaultsUpdated,
    PlanStatus,
)
from cora.recipe.features import update_plan_parameter_defaults
from cora.recipe.features.update_plan_parameter_defaults import (
    UpdatePlanParameterDefaults,
)

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _plan(
    *,
    parameter_defaults: dict[str, Any] | None = None,
    status: PlanStatus = PlanStatus.DEFINED,
) -> Plan:
    return Plan(
        id=uuid4(),
        name=PlanName("32-ID FlyScan"),
        practice_id=uuid4(),
        asset_ids=frozenset({uuid4()}),
        status=status,
        method_id=uuid4(),
        parameter_defaults=parameter_defaults if parameter_defaults is not None else {},
    )


def _schema() -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy_kev": {"type": "number", "minimum": 5, "maximum": 50},
            "exposure_ms": {"type": "integer", "minimum": 1},
        },
    }


@pytest.mark.unit
def test_decide_emits_event_when_setting_first_keys() -> None:
    state = _plan()
    events = update_plan_parameter_defaults.decide(
        state=state,
        command=UpdatePlanParameterDefaults(
            plan_id=state.id, parameter_defaults_patch={"energy_kev": 12.0}
        ),
        method_parameters_schema=_schema(),
        now=_NOW,
    )
    assert events == [
        PlanParameterDefaultsUpdated(
            plan_id=state.id,
            parameter_defaults={"energy_kev": 12.0},
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_event_payload_carries_post_merge_not_patch() -> None:
    """Locked design: event carries the FULL post-merge dict so each
    event is a self-contained audit record (5g-c precedent)."""
    state = _plan(parameter_defaults={"energy_kev": 12.0})
    events = update_plan_parameter_defaults.decide(
        state=state,
        command=UpdatePlanParameterDefaults(
            plan_id=state.id, parameter_defaults_patch={"exposure_ms": 250}
        ),
        method_parameters_schema=_schema(),
        now=_NOW,
    )
    assert len(events) == 1
    # Post-merge: BOTH keys present, not just the patch's exposure_ms.
    assert events[0].parameter_defaults == {"energy_kev": 12.0, "exposure_ms": 250}


@pytest.mark.unit
def test_decide_null_patch_value_deletes_key() -> None:
    """RFC 7396: null in patch deletes the key."""
    state = _plan(parameter_defaults={"energy_kev": 12.0, "exposure_ms": 100})
    events = update_plan_parameter_defaults.decide(
        state=state,
        command=UpdatePlanParameterDefaults(
            plan_id=state.id, parameter_defaults_patch={"exposure_ms": None}
        ),
        method_parameters_schema=_schema(),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].parameter_defaults == {"energy_kev": 12.0}


@pytest.mark.unit
def test_decide_no_op_when_merge_result_unchanged() -> None:
    """Re-submitting an empty patch on existing defaults: no event."""
    state = _plan(parameter_defaults={"energy_kev": 12.0})
    events = update_plan_parameter_defaults.decide(
        state=state,
        command=UpdatePlanParameterDefaults(plan_id=state.id, parameter_defaults_patch={}),
        method_parameters_schema=_schema(),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_decide_no_op_when_setting_same_value() -> None:
    state = _plan(parameter_defaults={"energy_kev": 12.0})
    events = update_plan_parameter_defaults.decide(
        state=state,
        command=UpdatePlanParameterDefaults(
            plan_id=state.id, parameter_defaults_patch={"energy_kev": 12.0}
        ),
        method_parameters_schema=_schema(),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_decide_raises_plan_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(PlanNotFoundError) as exc_info:
        update_plan_parameter_defaults.decide(
            state=None,
            command=UpdatePlanParameterDefaults(
                plan_id=target_id, parameter_defaults_patch={"energy_kev": 12.0}
            ),
            method_parameters_schema=_schema(),
            now=_NOW,
        )
    assert exc_info.value.plan_id == target_id


@pytest.mark.unit
def test_decide_raises_invalid_when_post_merge_violates_schema() -> None:
    state = _plan()
    with pytest.raises(InvalidPlanParameterDefaultsError):
        update_plan_parameter_defaults.decide(
            state=state,
            command=UpdatePlanParameterDefaults(
                plan_id=state.id, parameter_defaults_patch={"energy_kev": 1.0}
            ),
            method_parameters_schema=_schema(),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_strict_when_method_has_no_schema_with_non_empty_defaults() -> None:
    """Strict (post-6g audit reversal): Method-without-schema rejects
    non-empty defaults. Operator must declare a schema (an empty `{}`
    works) or omit the defaults. Aligns with 5g-c's strict zero-
    Capabilities posture and Ajv / Argo Workflows precedent."""
    state = _plan()
    with pytest.raises(InvalidPlanParameterDefaultsError) as exc_info:
        update_plan_parameter_defaults.decide(
            state=state,
            command=UpdatePlanParameterDefaults(
                plan_id=state.id,
                parameter_defaults_patch={"undeclared_key": "anything"},
            ),
            method_parameters_schema=None,
            now=_NOW,
        )
    assert "Method declares no parameters_schema" in exc_info.value.reason


@pytest.mark.unit
def test_decide_accepts_empty_defaults_when_method_has_no_schema() -> None:
    """Strict still allows trivial 'no contract + no values' state.
    No-op decider returns [] (defaults unchanged from empty)."""
    state = _plan()
    events = update_plan_parameter_defaults.decide(
        state=state,
        command=UpdatePlanParameterDefaults(plan_id=state.id, parameter_defaults_patch={}),
        method_parameters_schema=None,
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
@pytest.mark.parametrize(
    "lifecycle_status",
    [PlanStatus.DEFINED, PlanStatus.VERSIONED, PlanStatus.DEPRECATED],
)
def test_decide_accepts_defaults_update_in_any_lifecycle_state(
    lifecycle_status: PlanStatus,
) -> None:
    """Defaults updates are orthogonal to lifecycle: even Deprecated
    Plans accept defaults updates (operators may refine defaults
    after deprecation as audit-only data)."""
    state = _plan(status=lifecycle_status)
    events = update_plan_parameter_defaults.decide(
        state=state,
        command=UpdatePlanParameterDefaults(
            plan_id=state.id, parameter_defaults_patch={"energy_kev": 12.0}
        ),
        method_parameters_schema=_schema(),
        now=_NOW,
    )
    assert len(events) == 1
