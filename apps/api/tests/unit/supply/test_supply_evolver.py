"""Supply evolver: replay events to reconstruct state."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.supply.aggregates.supply import (
    Supply,
    SupplyMarkedAvailable,
    SupplyName,
    SupplyRegistered,
    SupplyScope,
    SupplyStatus,
    evolve,
    fold,
)

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_SUPPLY_ID = UUID("01900000-0000-7000-8000-000000005222")


# ---------- fold (genesis only) ----------


@pytest.mark.unit
def test_fold_empty_stream_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_genesis_only_lands_in_unknown() -> None:
    state = fold(
        [
            SupplyRegistered(
                supply_id=_SUPPLY_ID,
                scope="Beamline",
                kind="LiquidNitrogen",
                name="35-BM LN2 drop",
                occurred_at=_NOW,
            )
        ]
    )
    assert state == Supply(
        id=_SUPPLY_ID,
        scope=SupplyScope.BEAMLINE,
        kind="LiquidNitrogen",
        name=SupplyName("35-BM LN2 drop"),
        status=SupplyStatus.UNKNOWN,
    )


# ---------- fold (genesis + transition) ----------


@pytest.mark.unit
def test_fold_genesis_then_marked_available_lands_in_available() -> None:
    state = fold(
        [
            SupplyRegistered(
                supply_id=_SUPPLY_ID,
                scope="Facility",
                kind="PhotonBeam",
                name="APS storage-ring beam",
                occurred_at=_NOW,
            ),
            SupplyMarkedAvailable(
                supply_id=_SUPPLY_ID,
                from_status="Unknown",
                reason="control room confirms beam delivered",
                trigger="Operator",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.status == SupplyStatus.AVAILABLE
    # Identity + address preserved across the transition (additive-state pattern).
    assert state.id == _SUPPLY_ID
    assert state.scope == SupplyScope.FACILITY
    assert state.kind == "PhotonBeam"
    assert state.name.value == "APS storage-ring beam"


# ---------- transitions on empty state ----------


@pytest.mark.unit
def test_evolve_marked_available_on_empty_state_raises() -> None:
    """Transition events applied to an empty stream are corruption (require_state guard)."""
    with pytest.raises(ValueError, match="SupplyMarkedAvailable cannot be applied to empty state"):
        evolve(
            None,
            SupplyMarkedAvailable(
                supply_id=_SUPPLY_ID,
                from_status="Unknown",
                reason="r",
                trigger="Operator",
                occurred_at=_NOW,
            ),
        )


# ---------- evolver purity ----------


@pytest.mark.unit
def test_evolver_returns_new_state_does_not_mutate_input() -> None:
    initial = fold(
        [
            SupplyRegistered(
                supply_id=_SUPPLY_ID,
                scope="Beamline",
                kind="LiquidNitrogen",
                name="35-BM LN2",
                occurred_at=_NOW,
            )
        ]
    )
    assert initial is not None
    transitioned = evolve(
        initial,
        SupplyMarkedAvailable(
            supply_id=_SUPPLY_ID,
            from_status="Unknown",
            reason="r",
            trigger="Operator",
            occurred_at=_NOW,
        ),
    )
    # Initial state is untouched (frozen dataclass guarantee).
    assert initial.status == SupplyStatus.UNKNOWN
    assert transitioned.status == SupplyStatus.AVAILABLE
    assert transitioned is not initial
