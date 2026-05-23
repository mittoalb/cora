"""Application-handler tests for the `version_agent` slice."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.agent.aggregates.agent import (
    AgentCannotVersionError,
    AgentNotFoundError,
    ModelRef,
    event_type_name,
    to_payload,
)
from cora.agent.aggregates.agent.events import AgentDefined, AgentVersioned
from cora.agent.errors import UnauthorizedError
from cora.agent.features import version_agent
from cora.agent.features.version_agent import VersionAgent
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from tests.unit._helpers import build_deps as _build_deps_shared

_T0 = datetime(2026, 5, 16, 11, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_AGENT_ID = UUID("01900000-0000-7000-8000-00000000b001")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000000b002")
_VERSION_EVENT_ID = UUID("01900000-0000-7000-8000-00000000b003")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_VERSION_EVENT_ID],
        now=_T1,
        event_store=event_store,
        deny=deny,
    )


async def _seed_defined_agent(store: InMemoryEventStore) -> None:
    """Seed a Defined Agent at version 1 on the Agent stream."""
    genesis = AgentDefined(
        agent_id=_AGENT_ID,
        kind="RunDebriefer",
        name="Run Debrief",
        version="v1",
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        description=None,
        canonical_uri=None,
        prompt_template_id=None,
        capabilities=frozenset(),
        occurred_at=_T0,
    )
    await store.append(
        stream_type="Agent",
        stream_id=_AGENT_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(genesis),
                payload=to_payload(genesis),
                occurred_at=genesis.occurred_at,
                event_id=_GENESIS_EVENT_ID,
                command_name="DefineAgent",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


@pytest.mark.unit
async def test_handler_versions_a_defined_agent() -> None:
    store = InMemoryEventStore()
    await _seed_defined_agent(store)
    deps = _build_deps(event_store=store)
    handler = version_agent.bind(deps)
    await handler(
        VersionAgent(agent_id=_AGENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Agent", _AGENT_ID)
    assert version == 2
    assert events[-1].event_type == "AgentVersioned"
    assert events[-1].payload["version"] == "v1"


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    await _seed_defined_agent(store)
    deps = _build_deps(event_store=store)
    handler = version_agent.bind(deps)
    result = await handler(
        VersionAgent(agent_id=_AGENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_raises_not_found_for_unknown_agent() -> None:
    deps = _build_deps()
    handler = version_agent.bind(deps)
    with pytest.raises(AgentNotFoundError):
        await handler(
            VersionAgent(agent_id=_AGENT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_version_when_already_versioned() -> None:
    store = InMemoryEventStore()
    await _seed_defined_agent(store)
    # Apply a Versioned event on top.
    versioned = AgentVersioned(agent_id=_AGENT_ID, version="v1", occurred_at=_T1)
    await store.append(
        stream_type="Agent",
        stream_id=_AGENT_ID,
        expected_version=1,
        events=[
            to_new_event(
                event_type=event_type_name(versioned),
                payload=to_payload(versioned),
                occurred_at=versioned.occurred_at,
                event_id=UUID("01900000-0000-7000-8000-00000000b099"),
                command_name="VersionAgent",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )
    deps = _build_deps(event_store=store)
    handler = version_agent.bind(deps)
    with pytest.raises(AgentCannotVersionError):
        await handler(
            VersionAgent(agent_id=_AGENT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denies_via_authorize_port() -> None:
    deps = _build_deps(deny=True)
    handler = version_agent.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            VersionAgent(agent_id=_AGENT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denied_does_not_write_to_stream() -> None:
    """Authorize-denial MUST NOT mutate the Agent stream.

    Mirrors `test_define_agent_handler.test_handler_denied_does_not_write_either_stream`;
    closes gate-review test-coverage P1 for the transition handler.
    """
    store = InMemoryEventStore()
    await _seed_defined_agent(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = version_agent.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            VersionAgent(agent_id=_AGENT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Agent", _AGENT_ID)
    assert version == 1  # only the seeded genesis remains
    assert len(events) == 1
    assert events[0].event_type == "AgentDefined"
