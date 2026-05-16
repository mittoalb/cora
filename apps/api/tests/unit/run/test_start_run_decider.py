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
    AssetPort,
    PortDirection,
)
from cora.recipe.aggregates.plan import (
    Plan,
    PlanName,
    PlanStatus,
    PlanWireAssetNotBoundError,
    PlanWireDirectionMismatchError,
    PlanWirePortNotFoundError,
    PlanWireSignalTypeMismatchError,
    Wire,
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
        needed_capabilities_snapshot=frozenset({cap}),
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
        needed_capabilities_snapshot=frozenset({cap}),
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
        needed_capabilities_snapshot=frozenset({cap}),
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
        needed_capabilities_snapshot=frozenset({cap}),
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
            needed_capabilities_snapshot=frozenset(),
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
            needed_capabilities_snapshot=frozenset(),
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
            needed_capabilities_snapshot=frozenset(),
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
        needed_capabilities_snapshot=frozenset(),
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
            needed_capabilities_snapshot=frozenset(),
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
            needed_capabilities_snapshot=frozenset({needed_cap}),
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
        needed_capabilities_snapshot=frozenset({cap1, cap2}),
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
            needed_capabilities_snapshot=frozenset(),
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
        needed_capabilities_snapshot=frozenset(),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=new_id,
    )
    second = start_run.decide(
        state=None,
        command=cmd,
        context=context,
        needed_capabilities_snapshot=frozenset(),
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
    """Phase 6g-c: command's override_parameters + triggered_by carry
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
            override_parameters=overrides,
            triggered_by="operator:opid:5",
        ),
        context=context,
        needed_capabilities_snapshot=frozenset({cap}),
        effective_parameters=effective,
        method_parameters_schema=_energy_schema(),
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1
    started = events[0]
    assert started.override_parameters == overrides
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
            needed_capabilities_snapshot=frozenset({cap}),
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
            needed_capabilities_snapshot=frozenset({cap}),
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
        needed_capabilities_snapshot=frozenset({cap}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1
    assert events[0].effective_parameters == {}


# ---------- Phase 6h: Plan.wires re-validation at Run start ----------


@pytest.mark.unit
def test_decide_passes_when_plan_wires_endpoints_still_valid() -> None:
    """Happy path: a Plan with wires whose endpoints still exist on the
    bound Assets passes Run-start re-validation."""
    cap = uuid4()
    src_id = uuid4()
    tgt_id = uuid4()
    src_asset = Asset(
        id=src_id,
        name=AssetName("PandABox"),
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
        capabilities=frozenset({cap}),
        ports=frozenset(
            {AssetPort(name="trigger_out", direction=PortDirection.OUTPUT, signal_type="TTL")}
        ),
    )
    tgt_asset = Asset(
        id=tgt_id,
        name=AssetName("Camera"),
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
        capabilities=frozenset({cap}),
        ports=frozenset(
            {AssetPort(name="trigger_in", direction=PortDirection.INPUT, signal_type="TTL")}
        ),
    )
    plan = Plan(
        id=uuid4(),
        name=PlanName("Run"),
        practice_id=uuid4(),
        asset_ids=frozenset({src_id, tgt_id}),
        status=PlanStatus.DEFINED,
        method_id=uuid4(),
        wires=frozenset(
            {
                Wire(
                    source_asset_id=src_id,
                    source_port_name="trigger_out",
                    target_asset_id=tgt_id,
                    target_port_name="trigger_in",
                )
            }
        ),
    )
    context = RunStartContext(
        plan=plan,
        subject=_subject(),
        assets={src_id: src_asset, tgt_id: tgt_asset},
    )
    events = start_run.decide(
        state=None,
        command=StartRun(name="Run", plan_id=plan.id, subject_id=_subject().id),
        context=context,
        needed_capabilities_snapshot=frozenset({cap}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_rejects_when_plan_wire_references_removed_port() -> None:
    """Hot-swap regression: if an Asset port referenced by a Plan wire was
    removed between add_plan_wire and start_run, Run-start re-validation
    catches it. Strict-forward-reference applies at BOTH ends of the
    Wire's lifetime."""
    cap = uuid4()
    src_id = uuid4()
    tgt_id = uuid4()
    # Source asset MISSING the trigger_out port that the wire references.
    src_asset = Asset(
        id=src_id,
        name=AssetName("PandABox"),
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
        capabilities=frozenset({cap}),
        ports=frozenset(),  # port was removed!
    )
    tgt_asset = Asset(
        id=tgt_id,
        name=AssetName("Camera"),
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
        capabilities=frozenset({cap}),
        ports=frozenset(
            {AssetPort(name="trigger_in", direction=PortDirection.INPUT, signal_type="TTL")}
        ),
    )
    plan = Plan(
        id=uuid4(),
        name=PlanName("Run"),
        practice_id=uuid4(),
        asset_ids=frozenset({src_id, tgt_id}),
        status=PlanStatus.DEFINED,
        method_id=uuid4(),
        wires=frozenset(
            {
                Wire(
                    source_asset_id=src_id,
                    source_port_name="trigger_out",
                    target_asset_id=tgt_id,
                    target_port_name="trigger_in",
                )
            }
        ),
    )
    context = RunStartContext(
        plan=plan,
        subject=_subject(),
        assets={src_id: src_asset, tgt_id: tgt_asset},
    )
    with pytest.raises(PlanWirePortNotFoundError):
        start_run.decide(
            state=None,
            command=StartRun(name="Run", plan_id=plan.id, subject_id=_subject().id),
            context=context,
            needed_capabilities_snapshot=frozenset({cap}),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )


def _wire_capable_assets(
    src_id: UUID,
    tgt_id: UUID,
    *,
    cap: UUID,
    src_direction: PortDirection = PortDirection.OUTPUT,
    tgt_direction: PortDirection = PortDirection.INPUT,
    src_signal_type: str = "TTL",
    tgt_signal_type: str = "TTL",
) -> tuple[Asset, Asset]:
    """Helper: a pair of Assets each carrying one port suitable for a
    trigger_out -> trigger_in wire. Direction / signal_type knobs let
    drift-regression tests model "operator changed the port shape after
    the wire was added"."""
    src_asset = Asset(
        id=src_id,
        name=AssetName("PandABox"),
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
        capabilities=frozenset({cap}),
        ports=frozenset(
            {AssetPort(name="trigger_out", direction=src_direction, signal_type=src_signal_type)}
        ),
    )
    tgt_asset = Asset(
        id=tgt_id,
        name=AssetName("Camera"),
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
        capabilities=frozenset({cap}),
        ports=frozenset(
            {AssetPort(name="trigger_in", direction=tgt_direction, signal_type=tgt_signal_type)}
        ),
    )
    return src_asset, tgt_asset


def _trigger_wire(src_id: UUID, tgt_id: UUID) -> Wire:
    return Wire(
        source_asset_id=src_id,
        source_port_name="trigger_out",
        target_asset_id=tgt_id,
        target_port_name="trigger_in",
    )


@pytest.mark.unit
def test_decide_rejects_when_plan_wire_references_unbound_asset_at_run_start() -> None:
    """Hot-swap drift: the wire's target Asset was UNBOUND from Plan.asset_ids
    after the wire was added (e.g., operator re-defined the Plan with a
    different asset set, or a future re-bind slice removed it). The Wire
    survives in Plan.wires; Run-start re-validation catches the orphan."""
    cap = uuid4()
    src_id = uuid4()
    tgt_id = uuid4()  # NOT in plan.asset_ids
    src_asset, tgt_asset = _wire_capable_assets(src_id, tgt_id, cap=cap)
    plan = Plan(
        id=uuid4(),
        name=PlanName("Run"),
        practice_id=uuid4(),
        asset_ids=frozenset({src_id}),  # only src is bound
        status=PlanStatus.DEFINED,
        method_id=uuid4(),
        wires=frozenset({_trigger_wire(src_id, tgt_id)}),
    )
    context = RunStartContext(
        plan=plan,
        subject=_subject(),
        assets={src_id: src_asset, tgt_id: tgt_asset},
    )
    with pytest.raises(PlanWireAssetNotBoundError) as exc_info:
        start_run.decide(
            state=None,
            command=StartRun(name="Run", plan_id=plan.id, subject_id=_subject().id),
            context=context,
            needed_capabilities_snapshot=frozenset({cap}),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )
    assert tgt_id in exc_info.value.missing_asset_ids


@pytest.mark.unit
def test_decide_rejects_when_plan_wire_target_port_direction_flipped() -> None:
    """Hot-swap drift: the target port was removed and re-added with
    direction=OUTPUT after the wire was added. Run-start re-validation
    catches the direction violation."""
    cap = uuid4()
    src_id = uuid4()
    tgt_id = uuid4()
    src_asset, tgt_asset = _wire_capable_assets(
        src_id, tgt_id, cap=cap, tgt_direction=PortDirection.OUTPUT
    )
    plan = Plan(
        id=uuid4(),
        name=PlanName("Run"),
        practice_id=uuid4(),
        asset_ids=frozenset({src_id, tgt_id}),
        status=PlanStatus.DEFINED,
        method_id=uuid4(),
        wires=frozenset({_trigger_wire(src_id, tgt_id)}),
    )
    context = RunStartContext(
        plan=plan,
        subject=_subject(),
        assets={src_id: src_asset, tgt_id: tgt_asset},
    )
    with pytest.raises(PlanWireDirectionMismatchError):
        start_run.decide(
            state=None,
            command=StartRun(name="Run", plan_id=plan.id, subject_id=_subject().id),
            context=context,
            needed_capabilities_snapshot=frozenset({cap}),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_when_plan_wire_signal_type_changed() -> None:
    """Hot-swap drift: the target port was removed and re-added with a
    different signal_type after the wire was added. Run-start re-
    validation catches the type mismatch."""
    cap = uuid4()
    src_id = uuid4()
    tgt_id = uuid4()
    src_asset, tgt_asset = _wire_capable_assets(src_id, tgt_id, cap=cap, tgt_signal_type="LVDS")
    plan = Plan(
        id=uuid4(),
        name=PlanName("Run"),
        practice_id=uuid4(),
        asset_ids=frozenset({src_id, tgt_id}),
        status=PlanStatus.DEFINED,
        method_id=uuid4(),
        wires=frozenset({_trigger_wire(src_id, tgt_id)}),
    )
    context = RunStartContext(
        plan=plan,
        subject=_subject(),
        assets={src_id: src_asset, tgt_id: tgt_asset},
    )
    with pytest.raises(PlanWireSignalTypeMismatchError) as exc_info:
        start_run.decide(
            state=None,
            command=StartRun(name="Run", plan_id=plan.id, subject_id=_subject().id),
            context=context,
            needed_capabilities_snapshot=frozenset({cap}),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.source_signal_type == "TTL"
    assert exc_info.value.target_signal_type == "LVDS"


@pytest.mark.unit
def test_decide_revalidation_fails_fast_on_first_invalid_wire_in_a_set() -> None:
    """Multi-wire selectivity: the re-validation loop iterates wires;
    when wire #1 is valid and wire #2 is broken (port removed), the
    decider raises on wire #2 — wire #1 doesn't mask the failure.
    Pinned because the loop in start_run.decider uses a plain `for`
    that re-raises on the first violator (no exception aggregation)."""
    cap = uuid4()
    src_id = uuid4()
    tgt_id_1 = uuid4()
    tgt_id_2 = uuid4()
    # Two valid Asset pairs; tgt_id_2 ports removed (empty ports set).
    src_asset = Asset(
        id=src_id,
        name=AssetName("PandABox"),
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
        capabilities=frozenset({cap}),
        ports=frozenset(
            {
                AssetPort(name="trigger_out_1", direction=PortDirection.OUTPUT, signal_type="TTL"),
                AssetPort(name="trigger_out_2", direction=PortDirection.OUTPUT, signal_type="TTL"),
            }
        ),
    )
    tgt_asset_1 = Asset(
        id=tgt_id_1,
        name=AssetName("Camera1"),
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
        capabilities=frozenset({cap}),
        ports=frozenset(
            {AssetPort(name="trigger_in", direction=PortDirection.INPUT, signal_type="TTL")}
        ),
    )
    # tgt_2 is BOUND but its port was removed (drift).
    tgt_asset_2 = Asset(
        id=tgt_id_2,
        name=AssetName("Camera2"),
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
        capabilities=frozenset({cap}),
        ports=frozenset(),  # port removed since wire-add
    )
    wire_valid = Wire(
        source_asset_id=src_id,
        source_port_name="trigger_out_1",
        target_asset_id=tgt_id_1,
        target_port_name="trigger_in",
    )
    wire_broken = Wire(
        source_asset_id=src_id,
        source_port_name="trigger_out_2",
        target_asset_id=tgt_id_2,
        target_port_name="trigger_in",  # this port no longer exists
    )
    plan = Plan(
        id=uuid4(),
        name=PlanName("Run"),
        practice_id=uuid4(),
        asset_ids=frozenset({src_id, tgt_id_1, tgt_id_2}),
        status=PlanStatus.DEFINED,
        method_id=uuid4(),
        wires=frozenset({wire_valid, wire_broken}),
    )
    context = RunStartContext(
        plan=plan,
        subject=_subject(),
        assets={src_id: src_asset, tgt_id_1: tgt_asset_1, tgt_id_2: tgt_asset_2},
    )
    with pytest.raises(PlanWirePortNotFoundError) as exc_info:
        start_run.decide(
            state=None,
            command=StartRun(name="Run", plan_id=plan.id, subject_id=_subject().id),
            context=context,
            needed_capabilities_snapshot=frozenset({cap}),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )
    # The broken wire's target port name must appear in the diagnostic.
    assert any("trigger_in" in entry[1] for entry in exc_info.value.missing)
