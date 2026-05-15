"""ProcedureName VO + ProcedureStatus enum + Operation BC error class tests."""

from uuid import uuid4

import pytest

from cora.operation.aggregates.procedure import (
    PROCEDURE_NAME_MAX_LENGTH,
    InvalidProcedureKindError,
    InvalidProcedureNameError,
    ProcedureAlreadyExistsError,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedureStatus,
)

# ---------- ProcedureName VO ----------


@pytest.mark.unit
def test_procedure_name_trims_whitespace() -> None:
    assert ProcedureName("  Vessel-A bakeout  ").value == "Vessel-A bakeout"


@pytest.mark.unit
def test_procedure_name_rejects_empty() -> None:
    with pytest.raises(InvalidProcedureNameError):
        ProcedureName("")


@pytest.mark.unit
def test_procedure_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidProcedureNameError):
        ProcedureName("   ")


@pytest.mark.unit
def test_procedure_name_accepts_max_length() -> None:
    name = "x" * PROCEDURE_NAME_MAX_LENGTH
    assert ProcedureName(name).value == name


@pytest.mark.unit
def test_procedure_name_rejects_over_max_length() -> None:
    with pytest.raises(InvalidProcedureNameError):
        ProcedureName("x" * (PROCEDURE_NAME_MAX_LENGTH + 1))


# ---------- ProcedureStatus enum ----------


@pytest.mark.unit
def test_procedure_status_values_locked() -> None:
    """Pin the 5-state FSM values; future additions must be a deliberate test edit.
    The FSM was REVISED from BC map's `Idle/Starting/Running/Verifying/Complete/Aborted`
    per standards-corpus research at [[project_operation_design]]: Verifying is NOT
    standards-blessed at FSM level; transient states deferred per Run BC precedent."""
    assert ProcedureStatus.DEFINED.value == "Defined"
    assert ProcedureStatus.RUNNING.value == "Running"
    assert ProcedureStatus.COMPLETED.value == "Completed"
    assert ProcedureStatus.ABORTED.value == "Aborted"
    assert ProcedureStatus.TRUNCATED.value == "Truncated"
    assert {s.value for s in ProcedureStatus} == {
        "Defined",
        "Running",
        "Completed",
        "Aborted",
        "Truncated",
    }


# ---------- Error class shapes ----------


@pytest.mark.unit
def test_invalid_procedure_name_error_carries_value() -> None:
    err = InvalidProcedureNameError("")
    assert err.value == ""
    assert "1-200" in str(err)


@pytest.mark.unit
def test_invalid_procedure_kind_error_carries_value() -> None:
    err = InvalidProcedureKindError("x" * 51)
    assert err.value == "x" * 51
    assert "1-50" in str(err)


@pytest.mark.unit
def test_procedure_already_exists_error_carries_id() -> None:
    procedure_id = uuid4()
    err = ProcedureAlreadyExistsError(procedure_id)
    assert err.procedure_id == procedure_id
    assert str(procedure_id) in str(err)


@pytest.mark.unit
def test_procedure_not_found_error_carries_id() -> None:
    procedure_id = uuid4()
    err = ProcedureNotFoundError(procedure_id)
    assert err.procedure_id == procedure_id
    assert str(procedure_id) in str(err)
