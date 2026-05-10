"""Unit tests for the cross-BC `to_new_event` envelope builder.

The function takes an aggregate-agnostic (event_type, payload,
occurred_at) triple plus the cross-cutting envelope fields and
returns a `NewEvent`. Per-aggregate tests only cover their
`event_type_name`, `to_payload`, and `from_stored` helpers; the
envelope shape lives in this single test file.

End-to-end coverage of the envelope (including correct discriminator
and payload from real domain events) is in the per-handler tests
(`test_register_actor_handler`, `test_define_zone_handler`,
`test_define_conduit_handler`) and integration tests against
PostgresEventStore.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.event_envelope import to_new_event

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_builds_new_event_with_all_required_fields() -> None:
    event_id = uuid4()
    correlation_id = uuid4()
    payload: dict[str, object] = {"foo": "bar", "n": 1}

    new_event = to_new_event(
        event_type="SomethingHappened",
        payload=payload,
        occurred_at=_NOW,
        event_id=event_id,
        command_name="DoSomething",
        correlation_id=correlation_id,
    )

    assert new_event.event_id == event_id
    assert new_event.event_type == "SomethingHappened"
    assert new_event.schema_version == 1  # default
    assert new_event.payload == payload
    assert new_event.occurred_at == _NOW
    assert new_event.correlation_id == correlation_id
    assert new_event.causation_id is None  # default when not supplied
    assert new_event.metadata == {"command": "DoSomething"}


@pytest.mark.unit
def test_propagates_causation_id_when_supplied() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    new_event = to_new_event(
        event_type="SomethingHappened",
        payload={},
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="DoSomething",
        correlation_id=uuid4(),
        causation_id=causation,
    )
    assert new_event.causation_id == causation


@pytest.mark.unit
def test_metadata_holds_only_command_name() -> None:
    """Pin the `metadata` shape today so a future caller that adds
    fields here has to update this test (and therefore think about
    whether a metadata kwarg is the right API)."""
    new_event = to_new_event(
        event_type="X",
        payload={},
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="DoX",
        correlation_id=uuid4(),
    )
    assert new_event.metadata == {"command": "DoX"}
    assert set(new_event.metadata.keys()) == {"command"}


@pytest.mark.unit
def test_default_schema_version_is_one() -> None:
    new_event = to_new_event(
        event_type="X",
        payload={},
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="DoX",
        correlation_id=uuid4(),
    )
    assert new_event.schema_version == 1


@pytest.mark.unit
def test_explicit_schema_version_overrides_default() -> None:
    """Once the schema-evolution policy escalates a payload to v2, the
    handler bumps `schema_version=2` per CONTRIBUTING.md. Today no
    aggregate has done so; this test pins the override path."""
    new_event = to_new_event(
        event_type="X",
        payload={},
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="DoX",
        correlation_id=uuid4(),
        schema_version=2,
    )
    assert new_event.schema_version == 2


@pytest.mark.unit
def test_payload_is_stored_unchanged() -> None:
    """Pin that the function does NOT copy / transform the payload
    dict — caller's `to_payload(event)` is the single home for any
    serialization logic. If we ever need to deep-copy here, this test
    should change deliberately."""
    payload = {"k": "v", "nested": {"a": 1}}
    new_event = to_new_event(
        event_type="X",
        payload=payload,
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="DoX",
        correlation_id=uuid4(),
    )
    assert new_event.payload is payload
