"""Property-based tests for `register_procedure.decide` (Operation BC).

Mirrors the Access / Trust decider-PBT pattern on the Operation BC
create-style command with an optional `capability` cross-BC kwarg.
Universal claims across generated inputs:

  - state=None + capability_id=None + valid command emits a single
    ProcedureRegistered with the injected ids / now and trimmed
    name + kind.
  - state=Procedure always raises ProcedureAlreadyExistsError.
  - capability_id set + capability=None always raises
    CapabilityNotFoundError (cross-BC existence guard).
  - capability_id set + Capability without ExecutorShape.PROCEDURE
    always raises ProcedureCapabilityExecutorMismatchError.
  - Pure: same (state, command, capability, now, new_id) returns the
    same events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.operation.aggregates.procedure import (
    PROCEDURE_KIND_MAX_LENGTH,
    PROCEDURE_NAME_MAX_LENGTH,
    Procedure,
    ProcedureAlreadyExistsError,
    ProcedureCapabilityExecutorMismatchError,
    ProcedureName,
    ProcedureRegistered,
    ProcedureStatus,
)
from cora.operation.features import register_procedure
from cora.operation.features.register_procedure import RegisterProcedure
from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityCode,
    CapabilityName,
    CapabilityNotFoundError,
    ExecutorShape,
)
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NAME = printable_ascii_text(min_size=1, max_size=PROCEDURE_NAME_MAX_LENGTH)
_KIND = printable_ascii_text(min_size=1, max_size=PROCEDURE_KIND_MAX_LENGTH)
_TARGET_ASSET_IDS = st.frozensets(st.uuids(), max_size=4)


def _procedure(procedure_id: UUID) -> Procedure:
    return Procedure(
        id=procedure_id,
        name=ProcedureName("existing"),
        kind="alignment",
        target_asset_ids=frozenset(),
        parent_run_id=None,
        status=ProcedureStatus.DEFINED,
    )


@pytest.mark.unit
@given(
    name=_NAME,
    kind=_KIND,
    target_asset_ids=_TARGET_ASSET_IDS,
    parent_run_id=st.one_of(st.none(), st.uuids()),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_procedure_emits_exactly_one_event_with_injected_fields(
    name: str,
    kind: str,
    target_asset_ids: frozenset[UUID],
    parent_run_id: UUID | None,
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty stream + no capability binding + valid command -> single
    ProcedureRegistered with injected ids/time and trimmed text."""
    command = RegisterProcedure(
        name=name,
        kind=kind,
        target_asset_ids=target_asset_ids,
        parent_run_id=parent_run_id,
    )
    events = register_procedure.decide(state=None, command=command, now=now, new_id=new_id)
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, ProcedureRegistered)
    assert event.procedure_id == new_id
    assert event.name == name
    assert event.kind == kind
    assert set(event.target_asset_ids) == target_asset_ids
    assert event.parent_run_id == parent_run_id
    assert event.occurred_at == now
    assert event.capability_id is None


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    name=_NAME,
    kind=_KIND,
    target_asset_ids=_TARGET_ASSET_IDS,
    parent_run_id=st.one_of(st.none(), st.uuids()),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_procedure_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    name: str,
    kind: str,
    target_asset_ids: frozenset[UUID],
    parent_run_id: UUID | None,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state -> ProcedureAlreadyExistsError, regardless of command."""
    command = RegisterProcedure(
        name=name,
        kind=kind,
        target_asset_ids=target_asset_ids,
        parent_run_id=parent_run_id,
    )
    with pytest.raises(ProcedureAlreadyExistsError) as exc:
        register_procedure.decide(
            state=_procedure(existing_id),
            command=command,
            now=now,
            new_id=new_id,
        )
    assert exc.value.procedure_id == existing_id


@pytest.mark.unit
@given(
    name=_NAME,
    kind=_KIND,
    target_asset_ids=_TARGET_ASSET_IDS,
    capability_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_procedure_with_capability_id_but_no_capability_raises_not_found(
    name: str,
    kind: str,
    target_asset_ids: frozenset[UUID],
    capability_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """capability_id set + capability=None -> CapabilityNotFoundError."""
    command = RegisterProcedure(
        name=name,
        kind=kind,
        target_asset_ids=target_asset_ids,
        capability_id=capability_id,
    )
    with pytest.raises(CapabilityNotFoundError):
        register_procedure.decide(
            state=None,
            command=command,
            capability=None,
            now=now,
            new_id=new_id,
        )


@pytest.mark.unit
@given(
    name=_NAME,
    kind=_KIND,
    target_asset_ids=_TARGET_ASSET_IDS,
    capability_id=st.uuids(),
    capability_aggregate_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_procedure_with_capability_missing_procedure_shape_raises_mismatch(
    name: str,
    kind: str,
    target_asset_ids: frozenset[UUID],
    capability_id: UUID,
    capability_aggregate_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Capability without ExecutorShape.PROCEDURE -> mismatch error."""
    capability = Capability(
        id=capability_aggregate_id,
        code=CapabilityCode("cora.capability.x"),
        name=CapabilityName("X"),
        executor_shapes=frozenset({ExecutorShape.METHOD}),
    )
    command = RegisterProcedure(
        name=name,
        kind=kind,
        target_asset_ids=target_asset_ids,
        capability_id=capability_id,
    )
    with pytest.raises(ProcedureCapabilityExecutorMismatchError):
        register_procedure.decide(
            state=None,
            command=command,
            capability=capability,
            now=now,
            new_id=new_id,
        )


@pytest.mark.unit
@given(
    name=_NAME,
    kind=_KIND,
    target_asset_ids=_TARGET_ASSET_IDS,
    parent_run_id=st.one_of(st.none(), st.uuids()),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_procedure_is_pure_same_input_same_output(
    name: str,
    kind: str,
    target_asset_ids: frozenset[UUID],
    parent_run_id: UUID | None,
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return identical events (no clock leakage)."""
    command = RegisterProcedure(
        name=name,
        kind=kind,
        target_asset_ids=target_asset_ids,
        parent_run_id=parent_run_id,
    )
    first = register_procedure.decide(state=None, command=command, now=now, new_id=new_id)
    second = register_procedure.decide(state=None, command=command, now=now, new_id=new_id)
    assert first == second
