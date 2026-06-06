"""Unit tests for MethodRequiredRoleAdded + MethodRequiredRoleRemoved
event (de)serialization.

Pinned:
  - to_payload serializes required_ports sorted by (port_name, direction)
  - from_stored round-trips back to identical event
  - event_type_name returns the class name
  - older payloads missing optional/required_ports default cleanly
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.aggregates.method.events import (
    MethodRequiredRoleAdded,
    MethodRequiredRoleRemoved,
    event_type_name,
    from_stored,
    to_payload,
)

_NOW = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Method",
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
def test_event_type_name_for_required_role_added() -> None:
    evt = MethodRequiredRoleAdded(
        method_id=uuid4(),
        role_name="detector",
        family_id=uuid4(),
        required_ports=(),
        optional=False,
        occurred_at=_NOW,
    )
    assert event_type_name(evt) == "MethodRequiredRoleAdded"


@pytest.mark.unit
def test_event_type_name_for_required_role_removed() -> None:
    evt = MethodRequiredRoleRemoved(
        method_id=uuid4(),
        role_name="detector",
        occurred_at=_NOW,
    )
    assert event_type_name(evt) == "MethodRequiredRoleRemoved"


@pytest.mark.unit
def test_to_payload_required_role_added_sorts_required_ports() -> None:
    method_id = uuid4()
    family_id = uuid4()
    # Pass ports in deliberately out-of-order tuple; payload must sort.
    evt = MethodRequiredRoleAdded(
        method_id=method_id,
        role_name="detector",
        family_id=family_id,
        required_ports=(
            {"port_name": "trigger_in", "direction": "Input", "signal_type": "TTL"},
            {"port_name": "data_out", "direction": "Output", "signal_type": "Network"},
        ),
        optional=False,
        occurred_at=_NOW,
    )
    payload = to_payload(evt)
    assert payload["method_id"] == str(method_id)
    assert payload["role_name"] == "detector"
    assert payload["family_id"] == str(family_id)
    assert [p["port_name"] for p in payload["required_ports"]] == [
        "data_out",
        "trigger_in",
    ]
    assert payload["optional"] is False


@pytest.mark.unit
def test_to_payload_required_role_removed_minimal_shape() -> None:
    method_id = uuid4()
    evt = MethodRequiredRoleRemoved(
        method_id=method_id,
        role_name="detector",
        occurred_at=_NOW,
    )
    assert to_payload(evt) == {
        "method_id": str(method_id),
        "role_name": "detector",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_round_trips_required_role_added() -> None:
    method_id = uuid4()
    family_id = uuid4()
    payload = {
        "method_id": str(method_id),
        "role_name": "detector",
        "family_id": str(family_id),
        "required_ports": [
            {"port_name": "trigger_in", "direction": "Input", "signal_type": "TTL"},
        ],
        "optional": True,
        "occurred_at": _NOW.isoformat(),
    }
    evt = from_stored(_stored("MethodRequiredRoleAdded", payload))
    assert isinstance(evt, MethodRequiredRoleAdded)
    assert evt.method_id == method_id
    assert evt.role_name == "detector"
    assert evt.family_id == family_id
    assert evt.required_ports == (
        {"port_name": "trigger_in", "direction": "Input", "signal_type": "TTL"},
    )
    assert evt.optional is True


@pytest.mark.unit
def test_from_stored_round_trips_required_role_removed() -> None:
    method_id = uuid4()
    payload = {
        "method_id": str(method_id),
        "role_name": "detector",
        "occurred_at": _NOW.isoformat(),
    }
    evt = from_stored(_stored("MethodRequiredRoleRemoved", payload))
    assert isinstance(evt, MethodRequiredRoleRemoved)
    assert evt.method_id == method_id
    assert evt.role_name == "detector"


@pytest.mark.unit
def test_from_stored_required_role_added_defaults_missing_required_ports() -> None:
    """A future payload truncation or a hand-authored stored event
    without required_ports defaults to empty tuple. Pin so a typo
    in a downstream writer doesn't break replay."""
    method_id = uuid4()
    family_id = uuid4()
    payload = {
        "method_id": str(method_id),
        "role_name": "detector",
        "family_id": str(family_id),
        "occurred_at": _NOW.isoformat(),
        # required_ports + optional both absent
    }
    evt = from_stored(_stored("MethodRequiredRoleAdded", payload))
    assert isinstance(evt, MethodRequiredRoleAdded)
    assert evt.required_ports == ()
    assert evt.optional is False
