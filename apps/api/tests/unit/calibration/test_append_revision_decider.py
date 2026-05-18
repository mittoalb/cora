"""Unit tests for the `append_revision` slice's pure decider.

Pins the supersedes-must-exist invariant + STRICT value validation +
source-arc round-trip through serialize_source.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.calibration.aggregates.calibration import (
    AssertedSource,
    Calibration,
    CalibrationNotFoundError,
    CalibrationRevision,
    CalibrationStatus,
    ComputedSource,
    InvalidCalibrationValueError,
    MeasuredSource,
    SupersedesRevisionNotFoundError,
)
from cora.calibration.features import append_revision
from cora.calibration.features.append_revision import AppendRevision

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000ca2001")
_SUBSYSTEM_ID = UUID("01900000-0000-7000-8000-000000ca2002")
_CAL_ID = UUID("01900000-0000-7000-8000-000000ca2003")
_REV_ID_1 = UUID("01900000-0000-7000-8000-000000ca2004")
_REV_ID_2 = UUID("01900000-0000-7000-8000-000000ca2005")
_NEW_REV_ID = UUID("01900000-0000-7000-8000-000000ca2006")
_PROC_ID = UUID("01900000-0000-7000-8000-000000ca2007")
_DATASET_ID = UUID("01900000-0000-7000-8000-000000ca2008")


def _state(*, revisions: tuple[CalibrationRevision, ...] = ()) -> Calibration:
    return Calibration(
        id=_CAL_ID,
        subsystem_or_asset_id=_SUBSYSTEM_ID,
        quantity="rotation_center",
        operating_point={"energy_keV": 25.0, "optics_config": "5x"},
        description=None,
        revisions=revisions,
        defined_at=_NOW,
        last_revised_at=_NOW,
        defined_by_actor_id=_PRINCIPAL_ID,
    )


def _prior_revision(*, revision_id: UUID = _REV_ID_1) -> CalibrationRevision:
    return CalibrationRevision(
        revision_id=revision_id,
        value={"center_px": 1024.5},
        status=CalibrationStatus.PROVISIONAL,
        source=MeasuredSource(procedure_id=_PROC_ID),
        established_at=_NOW,
        established_by_actor_id=_PRINCIPAL_ID,
        decided_by_decision_id=None,
        supersedes_revision_id=None,
    )


@pytest.mark.unit
def test_decide_emits_revision_appended_for_valid_command() -> None:
    cmd = AppendRevision(
        calibration_id=_CAL_ID,
        value={"center_px": 1024.5},
        status=CalibrationStatus.PROVISIONAL,
        source=MeasuredSource(procedure_id=_PROC_ID),
    )
    events = append_revision.decide(
        state=_state(),
        command=cmd,
        now=_NOW,
        new_revision_id=_NEW_REV_ID,
        established_by_actor_id=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert event.revision_id == _NEW_REV_ID
    assert event.calibration_id == _CAL_ID
    assert event.status is CalibrationStatus.PROVISIONAL
    assert event.source_procedure_id == _PROC_ID
    assert event.source_dataset_id is None
    assert event.source_actor_id is None


@pytest.mark.unit
def test_decide_rejects_when_state_is_none() -> None:
    cmd = AppendRevision(
        calibration_id=_CAL_ID,
        value={"center_px": 1024.5},
        status=CalibrationStatus.PROVISIONAL,
        source=MeasuredSource(procedure_id=_PROC_ID),
    )
    with pytest.raises(CalibrationNotFoundError):
        append_revision.decide(
            state=None,
            command=cmd,
            now=_NOW,
            new_revision_id=_NEW_REV_ID,
            established_by_actor_id=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_decide_rejects_missing_required_value_key() -> None:
    """rotation_center value_schema requires center_px."""
    cmd = AppendRevision(
        calibration_id=_CAL_ID,
        value={"uncertainty_px": 0.3},  # missing center_px
        status=CalibrationStatus.PROVISIONAL,
        source=MeasuredSource(procedure_id=_PROC_ID),
    )
    with pytest.raises(InvalidCalibrationValueError):
        append_revision.decide(
            state=_state(),
            command=cmd,
            now=_NOW,
            new_revision_id=_NEW_REV_ID,
            established_by_actor_id=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_decide_rejects_empty_value() -> None:
    cmd = AppendRevision(
        calibration_id=_CAL_ID,
        value={},
        status=CalibrationStatus.PROVISIONAL,
        source=MeasuredSource(procedure_id=_PROC_ID),
    )
    with pytest.raises(InvalidCalibrationValueError):
        append_revision.decide(
            state=_state(),
            command=cmd,
            now=_NOW,
            new_revision_id=_NEW_REV_ID,
            established_by_actor_id=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_decide_rejects_supersedes_revision_not_on_aggregate() -> None:
    """Cross-aggregate supersession is forbidden."""
    cmd = AppendRevision(
        calibration_id=_CAL_ID,
        value={"center_px": 1024.5},
        status=CalibrationStatus.VERIFIED,
        source=ComputedSource(dataset_id=_DATASET_ID),
        supersedes_revision_id=uuid4(),  # not in revisions
    )
    with pytest.raises(SupersedesRevisionNotFoundError):
        append_revision.decide(
            state=_state(revisions=(_prior_revision(),)),
            command=cmd,
            now=_NOW,
            new_revision_id=_NEW_REV_ID,
            established_by_actor_id=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_decide_accepts_supersedes_revision_present_on_aggregate() -> None:
    """Direct derivation edge to a prior revision on the same aggregate."""
    cmd = AppendRevision(
        calibration_id=_CAL_ID,
        value={"center_px": 1023.8, "uncertainty_px": 0.1},
        status=CalibrationStatus.VERIFIED,
        source=ComputedSource(dataset_id=_DATASET_ID),
        supersedes_revision_id=_REV_ID_1,
    )
    events = append_revision.decide(
        state=_state(revisions=(_prior_revision(),)),
        command=cmd,
        now=_NOW,
        new_revision_id=_REV_ID_2,
        established_by_actor_id=_PRINCIPAL_ID,
    )
    assert events[0].supersedes_revision_id == _REV_ID_1
    assert events[0].source_dataset_id == _DATASET_ID
    assert events[0].source_procedure_id is None


@pytest.mark.unit
def test_decide_serializes_each_source_kind() -> None:
    """All three CalibrationSource arms round-trip into exclusive-arc fields."""
    for source, attr in [
        (MeasuredSource(procedure_id=_PROC_ID), "source_procedure_id"),
        (ComputedSource(dataset_id=_DATASET_ID), "source_dataset_id"),
        (AssertedSource(actor_id=_PRINCIPAL_ID), "source_actor_id"),
    ]:
        cmd = AppendRevision(
            calibration_id=_CAL_ID,
            value={"center_px": 1024.5},
            status=CalibrationStatus.PROVISIONAL,
            source=source,
        )
        events = append_revision.decide(
            state=_state(),
            command=cmd,
            now=_NOW,
            new_revision_id=_NEW_REV_ID,
            established_by_actor_id=_PRINCIPAL_ID,
        )
        # Exactly the named arc field is non-null; the other two are None.
        non_null = [
            f
            for f in ("source_procedure_id", "source_dataset_id", "source_actor_id")
            if getattr(events[0], f) is not None
        ]
        assert non_null == [attr]


@pytest.mark.unit
def test_decide_threads_decided_by_decision_id_through_to_event() -> None:
    decision_id = uuid4()
    cmd = AppendRevision(
        calibration_id=_CAL_ID,
        value={"center_px": 1024.5},
        status=CalibrationStatus.PROVISIONAL,
        source=MeasuredSource(procedure_id=_PROC_ID),
        decided_by_decision_id=decision_id,
    )
    events = append_revision.decide(
        state=_state(),
        command=cmd,
        now=_NOW,
        new_revision_id=_NEW_REV_ID,
        established_by_actor_id=_PRINCIPAL_ID,
    )
    assert events[0].decided_by_decision_id == decision_id
