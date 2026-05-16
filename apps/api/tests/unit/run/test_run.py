"""RunName + RunAbortReason + RunStopReason VOs + RunStatus enum + Run-side error class tests."""

from uuid import uuid4

import pytest

from cora.run.aggregates.run import (
    InvalidRunAbortReasonError,
    InvalidRunNameError,
    InvalidRunStopReasonError,
    PlanDeprecatedError,
    RunAbortReason,
    RunAlreadyExistsError,
    RunAssetDecommissionedError,
    RunCannotAbortError,
    RunCannotCompleteError,
    RunCannotHoldError,
    RunCannotResumeError,
    RunCannotStopError,
    RunCapabilitiesNotSatisfiedError,
    RunName,
    RunNotFoundError,
    RunStatus,
    RunStopReason,
    SubjectNotMountableError,
)

# ---------- RunName VO ----------


@pytest.mark.unit
def test_run_name_accepts_normal_string() -> None:
    name = RunName("32-ID FlyScan morning session")
    assert name.value == "32-ID FlyScan morning session"


@pytest.mark.unit
def test_run_name_trims_whitespace() -> None:
    name = RunName("  Dark field calibration 2026-05-11  ")
    assert name.value == "Dark field calibration 2026-05-11"


@pytest.mark.unit
def test_run_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidRunNameError):
        RunName("")


@pytest.mark.unit
def test_run_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidRunNameError):
        RunName("   \t\n   ")


@pytest.mark.unit
def test_run_name_rejects_too_long() -> None:
    with pytest.raises(InvalidRunNameError):
        RunName("a" * 201)


@pytest.mark.unit
def test_run_name_accepts_max_length() -> None:
    name = RunName("a" * 200)
    assert len(name.value) == 200


@pytest.mark.unit
def test_run_name_is_frozen() -> None:
    name = RunName("Standard run")
    with pytest.raises(AttributeError):
        name.value = "Other"  # type: ignore[misc]


# ---------- RunStatus enum ----------


@pytest.mark.unit
def test_run_status_has_full_lifecycle_fsm_in_6f4() -> None:
    """Phase 6f-4 closes the lifecycle FSM: Running (active steady-state)
    + Held (pause-state) + the four reachable terminals: Completed (happy
    path; single-source from Running), Aborted (emergency; multi-source),
    Stopped (controlled exit; multi-source), Truncated (partial-data
    cleanup for known-dead Runs; multi-source)."""
    assert {s.value for s in RunStatus} == {
        "Running",
        "Held",
        "Completed",
        "Aborted",
        "Stopped",
        "Truncated",
    }


@pytest.mark.unit
def test_run_status_is_str_enum_for_natural_serialization() -> None:
    assert isinstance(RunStatus.RUNNING, str)
    assert RunStatus.RUNNING == "Running"
    assert f"{RunStatus.RUNNING}" == "Running"
    assert RunStatus.HELD == "Held"
    assert RunStatus.COMPLETED == "Completed"
    assert RunStatus.ABORTED == "Aborted"
    assert RunStatus.STOPPED == "Stopped"
    assert RunStatus.TRUNCATED == "Truncated"


# ---------- Error classes ----------


@pytest.mark.unit
def test_run_already_exists_error_carries_run_id() -> None:
    run_id = uuid4()
    err = RunAlreadyExistsError(run_id)
    assert err.run_id == run_id
    assert str(run_id) in str(err)


@pytest.mark.unit
def test_run_not_found_error_carries_run_id() -> None:
    run_id = uuid4()
    err = RunNotFoundError(run_id)
    assert err.run_id == run_id
    assert str(run_id) in str(err)


@pytest.mark.unit
def test_plan_deprecated_error_carries_plan_id() -> None:
    plan_id = uuid4()
    err = PlanDeprecatedError(plan_id)
    assert err.plan_id == plan_id
    assert "Deprecated" in str(err)


@pytest.mark.unit
def test_subject_not_mountable_error_carries_subject_id_and_status() -> None:
    subject_id = uuid4()
    err = SubjectNotMountableError(subject_id, current_status="Removed")
    assert err.subject_id == subject_id
    assert err.current_status == "Removed"
    msg = str(err)
    assert "Mounted" in msg
    assert "Measured" in msg


@pytest.mark.unit
def test_run_asset_decommissioned_error_carries_asset_ids_list() -> None:
    asset_ids = [uuid4(), uuid4()]
    err = RunAssetDecommissionedError(asset_ids)
    assert err.asset_ids == asset_ids
    assert "Decommissioned" in str(err)


@pytest.mark.unit
def test_run_capabilities_not_satisfied_error_carries_missing_ids() -> None:
    missing = frozenset({uuid4()})
    err = RunCapabilitiesNotSatisfiedError(missing)
    assert err.missing_capability_ids == missing
    assert "missing capabilities" in str(err)


@pytest.mark.unit
def test_run_cannot_complete_error_carries_run_id_and_status() -> None:
    run_id = uuid4()
    err = RunCannotCompleteError(run_id, current_status=RunStatus.ABORTED)
    assert err.run_id == run_id
    assert err.current_status is RunStatus.ABORTED
    msg = str(err)
    assert "Aborted" in msg
    assert "Running" in msg


@pytest.mark.unit
def test_run_cannot_abort_error_carries_run_id_and_status() -> None:
    run_id = uuid4()
    err = RunCannotAbortError(run_id, current_status=RunStatus.COMPLETED)
    assert err.run_id == run_id
    assert err.current_status is RunStatus.COMPLETED
    msg = str(err)
    assert "Completed" in msg
    assert "Running" in msg


# ---------- RunAbortReason VO ----------


@pytest.mark.unit
def test_run_abort_reason_accepts_normal_string() -> None:
    reason = RunAbortReason("detector overheating")
    assert reason.value == "detector overheating"


@pytest.mark.unit
def test_run_abort_reason_trims_whitespace() -> None:
    reason = RunAbortReason("  beam dump unscheduled  ")
    assert reason.value == "beam dump unscheduled"


@pytest.mark.unit
def test_run_abort_reason_rejects_empty_string() -> None:
    with pytest.raises(InvalidRunAbortReasonError):
        RunAbortReason("")


@pytest.mark.unit
def test_run_abort_reason_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidRunAbortReasonError):
        RunAbortReason("   \t\n   ")


@pytest.mark.unit
def test_run_abort_reason_rejects_too_long() -> None:
    with pytest.raises(InvalidRunAbortReasonError):
        RunAbortReason("a" * 501)


@pytest.mark.unit
def test_run_abort_reason_accepts_max_length() -> None:
    reason = RunAbortReason("a" * 500)
    assert len(reason.value) == 500


@pytest.mark.unit
def test_run_abort_reason_is_frozen() -> None:
    reason = RunAbortReason("operator stop")
    with pytest.raises(AttributeError):
        reason.value = "Other"  # type: ignore[misc]


# ---------- 6f-3 transition error classes ----------


@pytest.mark.unit
def test_run_cannot_hold_error_carries_run_id_and_status() -> None:
    run_id = uuid4()
    err = RunCannotHoldError(run_id, current_status=RunStatus.HELD)
    assert err.run_id == run_id
    assert err.current_status is RunStatus.HELD
    msg = str(err)
    assert "Held" in msg
    assert "Running" in msg


@pytest.mark.unit
def test_run_cannot_resume_error_carries_run_id_and_status() -> None:
    run_id = uuid4()
    err = RunCannotResumeError(run_id, current_status=RunStatus.RUNNING)
    assert err.run_id == run_id
    assert err.current_status is RunStatus.RUNNING
    msg = str(err)
    assert "Running" in msg
    assert "Held" in msg


@pytest.mark.unit
def test_run_cannot_stop_error_carries_run_id_and_status() -> None:
    run_id = uuid4()
    err = RunCannotStopError(run_id, current_status=RunStatus.COMPLETED)
    assert err.run_id == run_id
    assert err.current_status is RunStatus.COMPLETED
    msg = str(err)
    assert "Completed" in msg
    assert "Running" in msg
    assert "Held" in msg


@pytest.mark.unit
def test_run_cannot_abort_error_now_lists_held_in_message() -> None:
    """6f-3 widened the abort source set to include Held."""
    run_id = uuid4()
    err = RunCannotAbortError(run_id, current_status=RunStatus.STOPPED)
    msg = str(err)
    assert "Running" in msg
    assert "Held" in msg


# ---------- RunStopReason VO ----------


@pytest.mark.unit
def test_run_stop_reason_accepts_normal_string() -> None:
    reason = RunStopReason("hit time budget cleanly")
    assert reason.value == "hit time budget cleanly"


@pytest.mark.unit
def test_run_stop_reason_trims_whitespace() -> None:
    reason = RunStopReason("  scan complete; ending early  ")
    assert reason.value == "scan complete; ending early"


@pytest.mark.unit
def test_run_stop_reason_rejects_empty_string() -> None:
    with pytest.raises(InvalidRunStopReasonError):
        RunStopReason("")


@pytest.mark.unit
def test_run_stop_reason_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidRunStopReasonError):
        RunStopReason("   \t\n   ")


@pytest.mark.unit
def test_run_stop_reason_rejects_too_long() -> None:
    with pytest.raises(InvalidRunStopReasonError):
        RunStopReason("a" * 501)


@pytest.mark.unit
def test_run_stop_reason_accepts_max_length() -> None:
    reason = RunStopReason("a" * 500)
    assert len(reason.value) == 500


@pytest.mark.unit
def test_run_stop_reason_is_frozen() -> None:
    reason = RunStopReason("operator stop")
    with pytest.raises(AttributeError):
        reason.value = "Other"  # type: ignore[misc]


# ---------- Phase 6i-c: Campaign-membership error classes ----------


@pytest.mark.unit
def test_run_cannot_join_campaign_error_carries_attrs() -> None:
    """RunCannotJoinCampaignError preserves run_id, campaign_id, and
    campaign_status for the BC's 409 exception handler + log
    aggregation."""
    from uuid import uuid4

    from cora.run.aggregates.run import RunCannotJoinCampaignError

    run_id = uuid4()
    campaign_id = uuid4()
    err = RunCannotJoinCampaignError(
        run_id=run_id,
        campaign_id=campaign_id,
        campaign_status="Closed",
    )
    assert err.run_id == run_id
    assert err.campaign_id == campaign_id
    assert err.campaign_status == "Closed"
    assert str(campaign_id) in str(err)
    assert "Closed" in str(err)


@pytest.mark.unit
def test_run_already_assigned_to_campaign_error_carries_attrs() -> None:
    """RunAlreadyAssignedToCampaignError carries both existing + new
    campaign ids for operator-facing remediation messages."""
    from uuid import uuid4

    from cora.run.aggregates.run import RunAlreadyAssignedToCampaignError

    run_id = uuid4()
    existing = uuid4()
    new = uuid4()
    err = RunAlreadyAssignedToCampaignError(
        run_id=run_id,
        existing_campaign_id=existing,
        new_campaign_id=new,
    )
    assert err.run_id == run_id
    assert err.existing_campaign_id == existing
    assert err.new_campaign_id == new
    assert str(existing) in str(err)
    assert str(new) in str(err)


# ---------- Phase 6j: adjust_run state field defaults + error classes ----------


@pytest.mark.unit
def test_run_dataclass_defaults_for_6j_adjustment_fields() -> None:
    """Phase 6j: last_adjusted_at + adjustment_count have safe defaults
    so legacy pre-6j streams fold cleanly."""
    from cora.run.aggregates.run import Run, RunName

    run = Run(
        id=uuid4(),
        name=RunName("R"),
        plan_id=uuid4(),
        subject_id=None,
    )
    assert run.last_adjusted_at is None
    assert run.adjustment_count == 0


@pytest.mark.unit
def test_run_cannot_adjust_error_carries_attrs() -> None:
    from cora.run.aggregates.run import RunCannotAdjustError

    run_id = uuid4()
    err = RunCannotAdjustError(run_id=run_id, current_status=RunStatus.COMPLETED)
    assert err.run_id == run_id
    assert err.current_status is RunStatus.COMPLETED
    assert "Completed" in str(err)
    assert str(run_id) in str(err)


@pytest.mark.unit
def test_invalid_run_adjustment_patch_error_carries_reason() -> None:
    from cora.run.aggregates.run import InvalidRunAdjustmentPatchError

    err = InvalidRunAdjustmentPatchError("must contain at least one change")
    assert err.reason == "must contain at least one change"
    assert "must contain at least one change" in str(err)


@pytest.mark.unit
def test_invalid_run_adjustment_schema_error_carries_detail() -> None:
    from cora.run.aggregates.run import InvalidRunAdjustmentSchemaError

    err = InvalidRunAdjustmentSchemaError("energy_kev: below minimum")
    assert err.detail == "energy_kev: below minimum"
    assert "energy_kev" in str(err)


@pytest.mark.unit
def test_invalid_run_adjust_reason_error_carries_value() -> None:
    from cora.run.aggregates.run import InvalidRunAdjustReasonError

    err = InvalidRunAdjustReasonError("   ")
    assert err.value == "   "
    assert "1-500" in str(err)
