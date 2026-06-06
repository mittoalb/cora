"""Round-trip tests for PlanRoleBound + PlanRoleUnbound events."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.aggregates.plan.events import (
    PlanRoleBound,
    PlanRoleUnbound,
    event_type_name,
    from_stored,
    to_payload,
)

_NOW = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Plan",
        stream_id=uuid4(),  # type: ignore[arg-type]
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_event_type_name_for_role_bound_returns_class_name() -> None:
    evt = PlanRoleBound(
        plan_id=uuid4(),
        role_name="detector",
        asset_id=uuid4(),
        occurred_at=_NOW,
    )
    assert event_type_name(evt) == "PlanRoleBound"


@pytest.mark.unit
def test_event_type_name_for_role_unbound_returns_class_name() -> None:
    evt = PlanRoleUnbound(plan_id=uuid4(), role_name="detector", occurred_at=_NOW)
    assert event_type_name(evt) == "PlanRoleUnbound"


@pytest.mark.unit
def test_to_payload_role_bound_shape_is_minimal() -> None:
    plan_id = uuid4()
    asset_id = uuid4()
    evt = PlanRoleBound(
        plan_id=plan_id,
        role_name="detector",
        asset_id=asset_id,
        occurred_at=_NOW,
    )
    assert to_payload(evt) == {
        "plan_id": str(plan_id),
        "role_name": "detector",
        "asset_id": str(asset_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_role_unbound_shape_is_minimal() -> None:
    plan_id = uuid4()
    evt = PlanRoleUnbound(plan_id=plan_id, role_name="detector", occurred_at=_NOW)
    assert to_payload(evt) == {
        "plan_id": str(plan_id),
        "role_name": "detector",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_round_trips_role_bound() -> None:
    plan_id = uuid4()
    asset_id = uuid4()
    payload: dict[str, Any] = {
        "plan_id": str(plan_id),
        "role_name": "detector",
        "asset_id": str(asset_id),
        "occurred_at": _NOW.isoformat(),
    }
    evt = from_stored(_stored("PlanRoleBound", payload))
    assert isinstance(evt, PlanRoleBound)
    assert evt.plan_id == plan_id
    assert evt.role_name == "detector"
    assert evt.asset_id == asset_id


@pytest.mark.unit
def test_from_stored_round_trips_role_unbound() -> None:
    plan_id = uuid4()
    payload: dict[str, Any] = {
        "plan_id": str(plan_id),
        "role_name": "detector",
        "occurred_at": _NOW.isoformat(),
    }
    evt = from_stored(_stored("PlanRoleUnbound", payload))
    assert isinstance(evt, PlanRoleUnbound)
    assert evt.plan_id == plan_id
    assert evt.role_name == "detector"
