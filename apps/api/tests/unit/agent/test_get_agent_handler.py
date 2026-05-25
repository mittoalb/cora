"""Application-handler tests for the `get_agent` query slice."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.agent.aggregates.agent import (
    AgentStatus,
    ModelRef,
    event_type_name,
    to_payload,
)
from cora.agent.aggregates.agent.events import AgentDefined
from cora.agent.errors import UnauthorizedError
from cora.agent.features import get_agent
from cora.agent.features.get_agent import GetAgent
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_T0 = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_AGENT_ID = UUID("01900000-0000-7000-8000-00000000d001")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000000d002")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[],  # query handler does not consume ids
        now=_T0,
        event_store=event_store,
        deny=deny,
    )


async def _seed_defined_agent(store: InMemoryEventStore) -> None:
    genesis = AgentDefined(
        agent_id=_AGENT_ID,
        kind="RunDebriefer",
        name="Run Debrief",
        version="v1",
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        description="Synthesises terminal Runs.",
        canonical_uri="https://example.org/agents/run-debrief",
        prompt_template_id=None,
        capabilities=frozenset({"summarize"}),
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
async def test_handler_returns_agent_on_hit() -> None:
    store = InMemoryEventStore()
    await _seed_defined_agent(store)
    deps = _build_deps(event_store=store)
    handler = get_agent.bind(deps)
    result = await handler(
        GetAgent(agent_id=_AGENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is not None
    assert result.agent.id == _AGENT_ID
    assert result.agent.kind.value == "RunDebriefer"
    assert result.agent.status is AgentStatus.DEFINED
    # In-memory deps have no pool -> projection-sourced timestamps absent.
    assert result.timestamps is None


@pytest.mark.unit
async def test_handler_returns_none_on_miss() -> None:
    deps = _build_deps()
    handler = get_agent.bind(deps)
    result = await handler(
        GetAgent(agent_id=_AGENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_denies_via_authorize_port() -> None:
    deps = _build_deps(deny=True)
    handler = get_agent.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            GetAgent(agent_id=_AGENT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
