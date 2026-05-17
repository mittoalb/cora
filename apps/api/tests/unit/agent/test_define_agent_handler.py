"""Application-handler tests for the `define_agent` slice (Phase 8f-a).

Focuses on the cross-BC atomic write: every successful `define_agent`
call writes ONE `AgentDefined` event on the Agent stream AND ONE
`ActorRegistered(kind=agent)` event on the Access stream with the
SAME id, via `EventStore.append_streams`.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.access.aggregates.actor import ActorKind
from cora.agent.aggregates.agent import ModelRef
from cora.agent.errors import UnauthorizedError
from cora.agent.features import define_agent
from cora.agent.features.define_agent import DefineAgent
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000a001")
_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-00000000a002")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-00000000a003")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        # define_agent consumes 3 ids: new agent_id + 1 event_id per stream.
        ids=[_NEW_ID, _AGENT_EVENT_ID, _ACTOR_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


def _command(**overrides: object) -> DefineAgent:
    base: dict[str, object] = {
        "kind": "RunDebrief",
        "name": "Run Debrief",
        "version": "v1",
        "model_ref": ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
    }
    base.update(overrides)
    return DefineAgent(**base)  # type: ignore[arg-type]


@pytest.mark.unit
async def test_handler_returns_generated_agent_id() -> None:
    deps = _build_deps()
    handler = define_agent.bind(deps)
    result = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_to_both_agent_and_actor_streams() -> None:
    """Cross-BC atomic write: AgentDefined on Agent stream AND
    ActorRegistered on Actor stream with the SAME id."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_agent.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    agent_events, agent_version = await store.load("Agent", _NEW_ID)
    actor_events, actor_version = await store.load("Actor", _NEW_ID)

    assert agent_version == 1
    assert actor_version == 1
    assert len(agent_events) == 1
    assert len(actor_events) == 1
    assert agent_events[0].event_type == "AgentDefined"
    assert actor_events[0].event_type == "ActorRegistered"


@pytest.mark.unit
async def test_handler_writes_kind_agent_on_actor_event() -> None:
    """The co-written Actor MUST be kind=agent (not human)."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_agent.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    actor_events, _ = await store.load("Actor", _NEW_ID)
    assert actor_events[0].payload["kind"] == ActorKind.AGENT.value


@pytest.mark.unit
async def test_handler_actor_name_mirrors_agent_name() -> None:
    """At genesis the Actor's display name matches the Agent's display name."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_agent.bind(deps)
    await handler(
        _command(name="  Run Debrief  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    actor_events, _ = await store.load("Actor", _NEW_ID)
    assert actor_events[0].payload["name"] == "Run Debrief"


@pytest.mark.unit
async def test_handler_agent_event_carries_full_command() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_agent.bind(deps)
    await handler(
        _command(
            description="Synthesises terminal Runs.",
            canonical_uri="https://example.org/agents/run-debrief",
            capabilities=frozenset({"summarize"}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    agent_events, _ = await store.load("Agent", _NEW_ID)
    payload = agent_events[0].payload
    assert payload["kind"] == "RunDebrief"
    assert payload["name"] == "Run Debrief"
    assert payload["version"] == "v1"
    assert payload["description"] == "Synthesises terminal Runs."
    assert payload["canonical_uri"] == "https://example.org/agents/run-debrief"
    assert payload["capabilities"] == ["summarize"]
    assert payload["model_ref"] == {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "snapshot_pin": None,
    }


@pytest.mark.unit
async def test_handler_propagates_envelope_fields_to_both_streams() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_agent.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    agent_events, _ = await store.load("Agent", _NEW_ID)
    actor_events, _ = await store.load("Actor", _NEW_ID)
    for events in (agent_events, actor_events):
        stored = events[0]
        assert stored.correlation_id == _CORRELATION_ID
        assert stored.causation_id is None


@pytest.mark.unit
async def test_handler_denies_via_authorize_port() -> None:
    deps = _build_deps(deny=True)
    handler = define_agent.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denied_does_not_write_either_stream() -> None:
    """Authorize-denial MUST NOT leave events on either stream."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = define_agent.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    agent_events, agent_version = await store.load("Agent", _NEW_ID)
    actor_events, actor_version = await store.load("Actor", _NEW_ID)
    assert agent_version == 0
    assert actor_version == 0
    assert agent_events == []
    assert actor_events == []
