"""Unit tests for the `start_run` slice's pure decider.

Second decider in the codebase that takes upstream aggregate state
as input (`RunStartContext`). These tests exercise the decider
directly with hand-built contexts; handler-level integration tests
live in test_start_run_handler.py.

Validation order pinned per gate-review Q5:
  1. State must be None (RunAlreadyExistsError)
  2. Plan not Deprecated (PlanDeprecatedError)
  3. Subject (if non-None) in {Mounted, Measured} (SubjectNotMountableError)
  4. No bound Asset Decommissioned (RunAssetDecommissionedError)
  5. Capability superset (RunCapabilitiesNotSatisfiedError)
  6. Name validation (InvalidRunNameError)
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetLevel,
    AssetLifecycle,
    AssetName,
)
from cora.recipe.aggregates.plan import (
    Plan,
    PlanName,
    PlanStatus,
)
from cora.run.aggregates.run import (
    InvalidRunNameError,
    InvalidRunParametersError,
    PlanDeprecatedError,
    Run,
    RunAlreadyExistsError,
    RunAssetDecommissionedError,
    RunCapabilitiesNotSatisfiedError,
    RunName,
    RunStarted,
    RunStatus,
    SubjectNotMountableError,
)
from cora.run.features import start_run
from cora.run.features.start_run import RunStartContext, StartRun
from cora.subject.aggregates.subject import Subject, SubjectName, SubjectStatus

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _plan(
    *,
    plan_id: UUID | None = None,
    practice_id: UUID | None = None,
    asset_ids: frozenset[UUID] | None = None,
    status: PlanStatus = PlanStatus.DEFINED,
) -> Plan:
    return Plan(
        id=plan_id or uuid4(),
        name=PlanName("32-ID FlyScan"),
        practice_id=practice_id or uuid4(),
        asset_ids=asset_ids or frozenset({uuid4()}),
        status=status,
    )


def _asset(
    *,
    asset_id: UUID | None = None,
    capabilities: frozenset[UUID] | None = None,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
) -> Asset:
    return Asset(
        id=asset_id or uuid4(),
        name=AssetName("EigerDetector"),
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        capabilities=capabilities if capabilities is not None else frozenset(),
    )


def _subject(
    *,
    subject_id: UUID | None = None,
    status: SubjectStatus = SubjectStatus.MOUNTED,
) -> Subject:
    return Subject(
        id=subject_id or uuid4(),
        name=SubjectName("PorousCeramicSample-A"),
        status=status,
    )


# ---------- Happy paths ----------


@pytest.mark.unit
def test_decide_emits_run_started_for_valid_sample_run() -> None:
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, capabilities=frozenset({cap}))
    subject = _subject()
    context = RunStartContext(plan=plan, subject=subject, assets={asset_id: asset})
    new_id = uuid4()
    events = start_run.decide(
        state=None,
        command=StartRun(name="Run", plan_id=plan.id, subject_id=subject.id),
        context=context,
        needs_capabilities_snapshot=frozenset({cap}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=new_id,
    )
    assert events == [
        RunStarted(
            run_id=new_id,
            name="Run",
            plan_id=plan.id,
            subject_id=subject.id,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_emits_run_started_for_dark_field_run_without_subject() -> None:
    """Calibration / dark-field runs have command.subject_id=None and
    context.subject=None — Subject precondition is skipped entirely."""
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, capabilities=frozenset({cap}))
    context = RunStartContext(plan=plan, subject=None, assets={asset_id: asset})
    new_id = uuid4()
    events = start_run.decide(
        state=None,
        command=StartRun(name="Dark field", plan_id=plan.id, subject_id=None),
        context=context,
        needs_capabilities_snapshot=frozenset({cap}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=new_id,
    )
    assert events == [
        RunStarted(
            run_id=new_id,
            name="Dark field",
            plan_id=plan.id,
            subject_id=None,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_accepts_subject_in_measured_state() -> None:
    """Re-measurement: Subject was already Measured by a prior Run; can be re-measured."""
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, capabilities=frozenset({cap}))
    subject = _subject(status=SubjectStatus.MEASURED)
    context = RunStartContext(plan=plan, subject=subject, assets={asset_id: asset})
    events = start_run.decide(
        state=None,
        command=StartRun(name="Re-measurement", plan_id=plan.id, subject_id=subject.id),
        context=context,
        needs_capabilities_snapshot=frozenset({cap}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_trims_run_name_via_value_object() -> None:
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, capabilities=frozenset({cap}))
    subject = _subject()
    context = RunStartContext(plan=plan, subject=subject, assets={asset_id: asset})
    events = start_run.decide(
        state=None,
        command=StartRun(name="  Run  ", plan_id=plan.id, subject_id=subject.id),
        context=context,
        needs_capabilities_snapshot=frozenset({cap}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].name == "Run"


# ---------- Validation: state pre-existing ----------


@pytest.mark.unit
def test_decide_raises_run_already_exists_when_state_is_not_none() -> None:
    existing_id = uuid4()
    state = Run(
        id=existing_id,
        name=RunName("Existing"),
        plan_id=uuid4(),
        subject_id=None,
        status=RunStatus.RUNNING,
    )
    plan = _plan()
    asset_id = next(iter(plan.asset_ids))
    asset = _asset(asset_id=asset_id)
    context = RunStartContext(plan=plan, subject=None, assets={asset_id: asset})
    with pytest.raises(RunAlreadyExistsError) as exc_info:
        start_run.decide(
            state=state,
            command=StartRun(name="X", plan_id=plan.id, subject_id=None),
            context=context,
            needs_capabilities_snapshot=frozenset(),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.run_id == existing_id


# ---------- Validation: deprecated plan ----------


@pytest.mark.unit
def test_decide_raises_plan_deprecated_when_plan_is_deprecated() -> None:
    plan = _plan(status=PlanStatus.DEPRECATED)
    asset_id = next(iter(plan.asset_ids))
    asset = _asset(asset_id=asset_id)
    context = RunStartContext(plan=plan, subject=None, assets={asset_id: asset})
    with pytest.raises(PlanDeprecatedError) as exc_info:
        start_run.decide(
            state=None,
            command=StartRun(name="X", plan_id=plan.id, subject_id=None),
            context=context,
            needs_capabilities_snapshot=frozenset(),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.plan_id == plan.id


# ---------- Validation: subject precondition ----------


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad_status",
    [
        SubjectStatus.RECEIVED,
        SubjectStatus.REMOVED,
        SubjectStatus.RETURNED,
        SubjectStatus.STORED,
        SubjectStatus.DISCARDED,
    ],
)
def test_decide_raises_subject_not_mountable_for_disallowed_subject_states(
    bad_status: SubjectStatus,
) -> None:
    plan = _plan()
    asset_id = next(iter(plan.asset_ids))
    asset = _asset(asset_id=asset_id)
    subject = _subject(status=bad_status)
    context = RunStartContext(plan=plan, subject=subject, assets={asset_id: asset})
    with pytest.raises(SubjectNotMountableError) as exc_info:
        start_run.decide(
            state=None,
            command=StartRun(name="X", plan_id=plan.id, subject_id=subject.id),
            context=context,
            needs_capabilities_snapshot=frozenset(),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.subject_id == subject.id
    assert exc_info.value.current_status == bad_status.value


@pytest.mark.unit
def test_decide_skips_subject_check_when_subject_id_is_none() -> None:
    """Calibration runs have no subject — precondition skipped entirely
    even if context.subject is None."""
    plan = _plan()
    asset_id = next(iter(plan.asset_ids))
    asset = _asset(asset_id=asset_id)
    context = RunStartContext(plan=plan, subject=None, assets={asset_id: asset})
    events = start_run.decide(
        state=None,
        command=StartRun(name="Dark field", plan_id=plan.id, subject_id=None),
        context=context,
        needs_capabilities_snapshot=frozenset(),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1


# ---------- Validation: decommissioned asset ----------


@pytest.mark.unit
def test_decide_raises_asset_decommissioned_when_any_bound_asset_decommissioned() -> None:
    a1 = uuid4()
    a2 = uuid4()
    plan = _plan(asset_ids=frozenset({a1, a2}))
    assets = {
        a1: _asset(asset_id=a1, lifecycle=AssetLifecycle.ACTIVE),
        a2: _asset(asset_id=a2, lifecycle=AssetLifecycle.DECOMMISSIONED),
    }
    context = RunStartContext(plan=plan, subject=None, assets=assets)
    with pytest.raises(RunAssetDecommissionedError) as exc_info:
        start_run.decide(
            state=None,
            command=StartRun(name="X", plan_id=plan.id, subject_id=None),
            context=context,
            needs_capabilities_snapshot=frozenset(),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )
    assert a2 in exc_info.value.asset_ids


# ---------- Validation: capabilities re-validation ----------


@pytest.mark.unit
def test_decide_raises_capabilities_not_satisfied_when_assets_drifted() -> None:
    """Method needs cap X; bound Asset's CURRENT capabilities don't include it.
    This catches drift between Plan-bind time and Run-start time."""
    needed_cap = uuid4()
    different_cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, capabilities=frozenset({different_cap}))
    context = RunStartContext(plan=plan, subject=None, assets={asset_id: asset})
    with pytest.raises(RunCapabilitiesNotSatisfiedError) as exc_info:
        start_run.decide(
            state=None,
            command=StartRun(name="X", plan_id=plan.id, subject_id=None),
            context=context,
            needs_capabilities_snapshot=frozenset({needed_cap}),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.missing_capability_ids == frozenset({needed_cap})


@pytest.mark.unit
def test_decide_uses_union_of_bound_assets_capabilities_for_satisfaction() -> None:
    """gate-review Q3-style check: union across bound Assets, not per-Asset."""
    cap1 = uuid4()
    cap2 = uuid4()
    a1 = uuid4()
    a2 = uuid4()
    plan = _plan(asset_ids=frozenset({a1, a2}))
    assets = {
        a1: _asset(asset_id=a1, capabilities=frozenset({cap1})),
        a2: _asset(asset_id=a2, capabilities=frozenset({cap2})),
    }
    context = RunStartContext(plan=plan, subject=None, assets=assets)
    events = start_run.decide(
        state=None,
        command=StartRun(name="X", plan_id=plan.id, subject_id=None),
        context=context,
        needs_capabilities_snapshot=frozenset({cap1, cap2}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1


# ---------- Validation: name ----------


@pytest.mark.unit
def test_decide_raises_invalid_run_name_for_whitespace_only() -> None:
    plan = _plan()
    asset_id = next(iter(plan.asset_ids))
    asset = _asset(asset_id=asset_id)
    context = RunStartContext(plan=plan, subject=None, assets={asset_id: asset})
    with pytest.raises(InvalidRunNameError):
        start_run.decide(
            state=None,
            command=StartRun(name="   ", plan_id=plan.id, subject_id=None),
            context=context,
            needs_capabilities_snapshot=frozenset(),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )


# ---------- Determinism ----------


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    plan = _plan()
    asset_id = next(iter(plan.asset_ids))
    asset = _asset(asset_id=asset_id)
    context = RunStartContext(plan=plan, subject=None, assets={asset_id: asset})
    new_id = uuid4()
    cmd = StartRun(name="X", plan_id=plan.id, subject_id=None)
    first = start_run.decide(
        state=None,
        command=cmd,
        context=context,
        needs_capabilities_snapshot=frozenset(),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=new_id,
    )
    second = start_run.decide(
        state=None,
        command=cmd,
        context=context,
        needs_capabilities_snapshot=frozenset(),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=new_id,
    )
    assert first == second


# ---------- 6g-c parameter validation + RunStarted payload extension ----------


_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _energy_schema() -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {"energy_kev": {"type": "number", "minimum": 5, "maximum": 50}},
    }


@pytest.mark.unit
def test_decide_emits_run_started_with_6gc_parameter_fields() -> None:
    """Phase 6g-c: command's parameter_overrides + triggered_by carry
    into the RunStarted event; effective_parameters comes from the
    handler-computed merge (passed in as a kwarg here)."""
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, capabilities=frozenset({cap}))
    subject = _subject()
    context = RunStartContext(plan=plan, subject=subject, assets={asset_id: asset})
    overrides: dict[str, Any] = {"energy_kev": 12.0}
    effective: dict[str, Any] = {"energy_kev": 12.0}

    events = start_run.decide(
        state=None,
        command=StartRun(
            name="Run",
            plan_id=plan.id,
            subject_id=subject.id,
            parameter_overrides=overrides,
            triggered_by="operator:opid:5",
        ),
        context=context,
        needs_capabilities_snapshot=frozenset({cap}),
        effective_parameters=effective,
        method_parameters_schema=_energy_schema(),
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1
    started = events[0]
    assert started.parameter_overrides == overrides
    assert started.effective_parameters == effective
    assert started.triggered_by == "operator:opid:5"


@pytest.mark.unit
def test_decide_raises_invalid_run_parameters_on_post_merge_violation() -> None:
    """Resolved (defaults + overrides) merge violates the Method's
    schema -> InvalidRunParametersError."""
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, capabilities=frozenset({cap}))
    subject = _subject()
    context = RunStartContext(plan=plan, subject=subject, assets={asset_id: asset})

    with pytest.raises(InvalidRunParametersError):
        start_run.decide(
            state=None,
            command=StartRun(name="Run", plan_id=plan.id, subject_id=subject.id),
            context=context,
            needs_capabilities_snapshot=frozenset({cap}),
            effective_parameters={"energy_kev": 1.0},  # below minimum=5
            method_parameters_schema=_energy_schema(),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_strict_when_method_schema_is_none_with_non_empty_effective() -> None:
    """Strict (post-6g audit reversal): Method without parameters_schema
    rejects non-empty effective dict. Pinned at the decider layer.
    Aligns with 5g-c's strict zero-Capabilities posture and Ajv /
    Argo Workflows precedent."""
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, capabilities=frozenset({cap}))
    subject = _subject()
    context = RunStartContext(plan=plan, subject=subject, assets={asset_id: asset})

    with pytest.raises(InvalidRunParametersError) as exc_info:
        start_run.decide(
            state=None,
            command=StartRun(name="Run", plan_id=plan.id, subject_id=subject.id),
            context=context,
            needs_capabilities_snapshot=frozenset({cap}),
            effective_parameters={"undeclared_key": "anything"},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )
    assert "Method declares no parameters_schema" in exc_info.value.reason


@pytest.mark.unit
def test_decide_accepts_no_schema_when_effective_is_empty() -> None:
    """Strict still allows the trivial 'no contract + no values'
    state: starting a Run with no overrides AND no Plan defaults
    against a no-schema Method is fine."""
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, capabilities=frozenset({cap}))
    subject = _subject()
    context = RunStartContext(plan=plan, subject=subject, assets={asset_id: asset})

    events = start_run.decide(
        state=None,
        command=StartRun(name="Run", plan_id=plan.id, subject_id=subject.id),
        context=context,
        needs_capabilities_snapshot=frozenset({cap}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1
    assert events[0].effective_parameters == {}
