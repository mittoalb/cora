"""Event (de)serialization round-trip tests for the Agent aggregate (Phase 8f-a)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.agent.aggregates.agent.events import (
    AgentDefined,
    AgentDeprecated,
    AgentVersioned,
    deserialize_model_ref,
    event_type_name,
    from_stored,
    serialize_model_ref,
    to_payload,
)
from cora.agent.aggregates.agent.state import ModelRef
from cora.infrastructure.ports.event_store import StoredEvent

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)


def _stored(
    event_type: str,
    payload: dict[str, object],
) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Agent",
        stream_id=uuid4(),
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


# ---------- ModelRef serialize / deserialize ----------


@pytest.mark.unit
def test_serialize_model_ref_full_triple() -> None:
    m = ModelRef(provider="anthropic", model="claude-sonnet-4-6", snapshot_pin="20251001")
    assert serialize_model_ref(m) == {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "snapshot_pin": "20251001",
    }


@pytest.mark.unit
def test_serialize_model_ref_null_snapshot_pin() -> None:
    m = ModelRef(provider="openai", model="o4-mini", snapshot_pin=None)
    assert serialize_model_ref(m) == {
        "provider": "openai",
        "model": "o4-mini",
        "snapshot_pin": None,
    }


@pytest.mark.unit
def test_deserialize_model_ref_round_trips() -> None:
    original = ModelRef(provider="anthropic", model="claude-sonnet-4-6", snapshot_pin="20251001")
    payload = serialize_model_ref(original)
    assert deserialize_model_ref(payload) == original


@pytest.mark.unit
def test_deserialize_model_ref_raises_on_missing_field() -> None:
    with pytest.raises(ValueError, match="Malformed ModelRef payload"):
        deserialize_model_ref({"provider": "anthropic"})  # missing 'model'


# ---------- event_type_name ----------


@pytest.mark.unit
def test_event_type_name_returns_class_name() -> None:
    e = AgentDefined(
        agent_id=uuid4(),
        kind="RunDebrief",
        name="Run Debrief",
        version="v1",
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        description=None,
        canonical_uri=None,
        prompt_template_id=None,
        capabilities=frozenset(),
        occurred_at=_NOW,
    )
    assert event_type_name(e) == "AgentDefined"


# ---------- AgentDefined serialize / deserialize ----------


@pytest.mark.unit
def test_to_payload_serializes_agent_defined_minimal() -> None:
    agent_id = uuid4()
    e = AgentDefined(
        agent_id=agent_id,
        kind="RunDebrief",
        name="Run Debrief",
        version="v1",
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        description=None,
        canonical_uri=None,
        prompt_template_id=None,
        capabilities=frozenset(),
        occurred_at=_NOW,
    )
    payload = to_payload(e)
    assert payload == {
        "agent_id": str(agent_id),
        "kind": "RunDebrief",
        "name": "Run Debrief",
        "version": "v1",
        "model_ref": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "snapshot_pin": None,
        },
        "description": None,
        "canonical_uri": None,
        "prompt_template_id": None,
        "capabilities": [],
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_agent_defined_full() -> None:
    agent_id = uuid4()
    template_id = uuid4()
    e = AgentDefined(
        agent_id=agent_id,
        kind="RunDebrief",
        name="Run Debrief",
        version="v1",
        model_ref=ModelRef(
            provider="anthropic", model="claude-sonnet-4-6", snapshot_pin="20251001"
        ),
        description="Synthesises terminal Runs.",
        canonical_uri="https://example.org/agents/run-debrief",
        prompt_template_id=template_id,
        capabilities=frozenset({"summarize", "categorize"}),
        occurred_at=_NOW,
    )
    payload = to_payload(e)
    assert payload["prompt_template_id"] == str(template_id)
    assert payload["capabilities"] == ["categorize", "summarize"]  # sorted for determinism
    assert payload["model_ref"]["snapshot_pin"] == "20251001"


@pytest.mark.unit
def test_round_trip_agent_defined_full() -> None:
    agent_id = uuid4()
    template_id = uuid4()
    original = AgentDefined(
        agent_id=agent_id,
        kind="RunDebrief",
        name="Run Debrief",
        version="v1",
        model_ref=ModelRef(
            provider="anthropic", model="claude-sonnet-4-6", snapshot_pin="20251001"
        ),
        description="Synthesises terminal Runs.",
        canonical_uri="https://example.org/agents/run-debrief",
        prompt_template_id=template_id,
        capabilities=frozenset({"summarize", "categorize"}),
        occurred_at=_NOW,
    )
    stored = _stored("AgentDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_round_trip_agent_defined_minimal() -> None:
    original = AgentDefined(
        agent_id=uuid4(),
        kind="RunDebrief",
        name="Run Debrief",
        version="v1",
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        description=None,
        canonical_uri=None,
        prompt_template_id=None,
        capabilities=frozenset(),
        occurred_at=_NOW,
    )
    stored = _stored("AgentDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_agent_defined_raises_on_missing_field() -> None:
    stored = _stored(
        "AgentDefined",
        {"agent_id": str(uuid4())},  # missing kind / name / etc.
    )
    with pytest.raises(ValueError, match="Malformed AgentDefined payload"):
        from_stored(stored)


# ---------- AgentVersioned ----------


@pytest.mark.unit
def test_to_payload_serializes_agent_versioned() -> None:
    agent_id = uuid4()
    e = AgentVersioned(agent_id=agent_id, version="v1", occurred_at=_NOW)
    assert to_payload(e) == {
        "agent_id": str(agent_id),
        "version": "v1",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_round_trip_agent_versioned() -> None:
    original = AgentVersioned(agent_id=uuid4(), version="v1", occurred_at=_NOW)
    stored = _stored("AgentVersioned", to_payload(original))
    assert from_stored(stored) == original


# ---------- AgentDeprecated ----------


@pytest.mark.unit
def test_to_payload_serializes_agent_deprecated_with_reason() -> None:
    agent_id = uuid4()
    e = AgentDeprecated(agent_id=agent_id, reason="model retired", occurred_at=_NOW)
    assert to_payload(e) == {
        "agent_id": str(agent_id),
        "reason": "model retired",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_agent_deprecated_without_reason() -> None:
    agent_id = uuid4()
    e = AgentDeprecated(agent_id=agent_id, reason=None, occurred_at=_NOW)
    assert to_payload(e) == {
        "agent_id": str(agent_id),
        "reason": None,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_round_trip_agent_deprecated() -> None:
    original = AgentDeprecated(agent_id=uuid4(), reason="model retired", occurred_at=_NOW)
    stored = _stored("AgentDeprecated", to_payload(original))
    assert from_stored(stored) == original


# ---------- Foreign event_type fails loud ----------


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    stored = _stored("SomethingElse", {})
    with pytest.raises(ValueError, match="Unknown AgentEvent event_type"):
        from_stored(stored)
