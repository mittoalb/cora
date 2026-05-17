"""Application-handler tests for the `resume_agent` slice (Phase 8f-c iter 2)."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.agent.aggregates.agent import (
    AgentCannotResumeError,
    AgentNotFoundError,
)
from cora.agent.errors import UnauthorizedError
from cora.agent.features import resume_agent
from cora.agent.features.resume_agent import ResumeAgent
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.agent._iter2_seed import seed_suspended_agent, seed_versioned_agent

_T0 = datetime(2026, 5, 17, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 17, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_T3 = datetime(2026, 5, 17, 13, 0, 0, tzinfo=UTC)
_AGENT_ID = UUID("01900000-0000-7000-8000-00000000e001")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000000e002")
_VERSION_EVENT_ID = UUID("01900000-0000-7000-8000-00000000e003")
_SUSPEND_EVENT_ID = UUID("01900000-0000-7000-8000-00000000e004")
_NEXT_EVENT_ID = UUID("01900000-0000-7000-8000-00000000e005")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEXT_EVENT_ID],
        now=_T3,
        event_store=event_store,
        deny=deny,
    )


@pytest.mark.unit
async def test_handler_resumes_a_suspended_agent() -> None:
    store = InMemoryEventStore()
    await seed_suspended_agent(
        store,
        agent_id=_AGENT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        version_event_id=_VERSION_EVENT_ID,
        suspend_event_id=_SUSPEND_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        versioned_at=_T1,
        suspended_at=_T2,
    )
    deps = _build_deps(event_store=store)
    handler = resume_agent.bind(deps)
    await handler(
        ResumeAgent(agent_id=_AGENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Agent", _AGENT_ID)
    assert version == 4
    assert events[-1].event_type == "AgentResumed"


@pytest.mark.unit
async def test_handler_raises_not_found_for_unknown_agent() -> None:
    deps = _build_deps()
    handler = resume_agent.bind(deps)
    with pytest.raises(AgentNotFoundError):
        await handler(
            ResumeAgent(agent_id=_AGENT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_resume_when_versioned() -> None:
    store = InMemoryEventStore()
    await seed_versioned_agent(
        store,
        agent_id=_AGENT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        version_event_id=_VERSION_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        versioned_at=_T1,
    )
    deps = _build_deps(event_store=store)
    handler = resume_agent.bind(deps)
    with pytest.raises(AgentCannotResumeError):
        await handler(
            ResumeAgent(agent_id=_AGENT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denied_does_not_write_to_stream() -> None:
    store = InMemoryEventStore()
    await seed_suspended_agent(
        store,
        agent_id=_AGENT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        version_event_id=_VERSION_EVENT_ID,
        suspend_event_id=_SUSPEND_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        versioned_at=_T1,
        suspended_at=_T2,
    )
    deps = _build_deps(event_store=store, deny=True)
    handler = resume_agent.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            ResumeAgent(agent_id=_AGENT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Agent", _AGENT_ID)
    assert version == 3  # untouched (Defined + Versioned + Suspended)
