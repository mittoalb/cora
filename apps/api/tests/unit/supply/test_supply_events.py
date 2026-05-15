"""SupplyEvent serialization round-trips: to_payload + from_stored."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.supply.aggregates.supply import (
    SupplyMarkedAvailable,
    SupplyRegistered,
    event_type_name,
    from_stored,
    to_payload,
)

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_SUPPLY_ID = UUID("01900000-0000-7000-8000-000000005111")


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Supply",
        stream_id=_SUPPLY_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


# ---------- SupplyRegistered ----------


@pytest.mark.unit
def test_supply_registered_event_type_name() -> None:
    event = SupplyRegistered(
        supply_id=_SUPPLY_ID,
        scope="Beamline",
        kind="LiquidNitrogen",
        name="35-BM LN2 drop",
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "SupplyRegistered"


@pytest.mark.unit
def test_supply_registered_to_payload() -> None:
    event = SupplyRegistered(
        supply_id=_SUPPLY_ID,
        scope="Beamline",
        kind="LiquidNitrogen",
        name="35-BM LN2 drop",
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "supply_id": str(_SUPPLY_ID),
        "scope": "Beamline",
        "kind": "LiquidNitrogen",
        "name": "35-BM LN2 drop",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_supply_registered_round_trip_via_from_stored() -> None:
    original = SupplyRegistered(
        supply_id=_SUPPLY_ID,
        scope="Facility",
        kind="PhotonBeam",
        name="APS storage-ring beam",
        occurred_at=_NOW,
    )
    rebuilt = from_stored(_stored("SupplyRegistered", to_payload(original)))
    assert rebuilt == original


# ---------- SupplyMarkedAvailable ----------


@pytest.mark.unit
def test_supply_marked_available_event_type_name() -> None:
    event = SupplyMarkedAvailable(
        supply_id=_SUPPLY_ID,
        from_status="Unknown",
        reason="operator walkdown",
        trigger="Operator",
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "SupplyMarkedAvailable"


@pytest.mark.unit
def test_supply_marked_available_to_payload() -> None:
    event = SupplyMarkedAvailable(
        supply_id=_SUPPLY_ID,
        from_status="Unknown",
        reason="operator walkdown",
        trigger="Operator",
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "supply_id": str(_SUPPLY_ID),
        "from_status": "Unknown",
        "reason": "operator walkdown",
        "trigger": "Operator",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_supply_marked_available_round_trip_via_from_stored() -> None:
    original = SupplyMarkedAvailable(
        supply_id=_SUPPLY_ID,
        from_status="Unknown",
        reason="operator confirms beam delivered after morning startup",
        trigger="Operator",
        occurred_at=_NOW,
    )
    rebuilt = from_stored(_stored("SupplyMarkedAvailable", to_payload(original)))
    assert rebuilt == original


# ---------- from_stored unknown event_type ----------


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    with pytest.raises(ValueError, match="Unknown SupplyEvent event_type"):
        from_stored(_stored("ImaginaryEvent", {"foo": "bar"}))
