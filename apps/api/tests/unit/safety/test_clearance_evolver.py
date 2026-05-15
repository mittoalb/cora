"""Clearance evolver: replay events to reconstruct state."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.safety.aggregates.clearance import (
    ClearanceKind,
    ClearanceRegistered,
    ClearanceStatus,
    SubjectBinding,
    evolve,
    fold,
)
from cora.safety.hazard_classification import RiskBand

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_CLEARANCE_ID = UUID("01900000-0000-7000-8000-000000011002")


def _genesis_event(*, with_optional: bool = False) -> ClearanceRegistered:
    sid = uuid4()
    return ClearanceRegistered(
        clearance_id=_CLEARANCE_ID,
        kind="ESAF",
        title="Pilot",
        bindings=({"kind": "Subject", "id": str(sid)},),
        declarations=(
            {
                "target": {"kind": "Subject", "id": str(sid)},
                "classifications": [{"kind": "RiskBand", "band": "Yellow"}],
                "mitigations": [],
                "notes": None,
            },
        ),
        risk_band="Yellow" if with_optional else None,
        external_id="ESAF-12345" if with_optional else None,
        valid_from=_NOW if with_optional else None,
        valid_until=None,
        parent_clearance_id=None,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_fold_empty_stream_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_genesis_only_lands_in_defined() -> None:
    state = fold([_genesis_event()])
    assert state is not None
    assert state.id == _CLEARANCE_ID
    assert state.kind == ClearanceKind.ESAF
    assert state.status == ClearanceStatus.DEFINED


@pytest.mark.unit
def test_fold_genesis_reconstructs_typed_bindings() -> None:
    state = fold([_genesis_event()])
    assert state is not None
    assert len(state.bindings) == 1
    binding = next(iter(state.bindings))
    assert isinstance(binding, SubjectBinding)


@pytest.mark.unit
def test_fold_genesis_with_optional_fields() -> None:
    state = fold([_genesis_event(with_optional=True)])
    assert state is not None
    assert state.risk_band == RiskBand.YELLOW
    assert state.external_id == "ESAF-12345"
    assert state.valid_from == _NOW


@pytest.mark.unit
def test_evolver_returns_new_state_does_not_mutate_input() -> None:
    """Genesis only at 11a-a; verify the genesis arm is non-mutating."""
    state1 = evolve(None, _genesis_event())
    state2 = evolve(None, _genesis_event())
    # Each call returns a fresh frozen instance
    assert state1 is not state2
    assert state1.id == state2.id


@pytest.mark.unit
def test_fold_reconstructs_declarations() -> None:
    state = fold([_genesis_event()])
    assert state is not None
    assert len(state.declarations) == 1
    decl = next(iter(state.declarations))
    assert RiskBand.YELLOW in decl.classifications
