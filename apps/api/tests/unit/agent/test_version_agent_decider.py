"""Pure-decider tests for the `version_agent` slice (Phase 8f-a)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotVersionError,
    AgentKind,
    AgentName,
    AgentNotFoundError,
    AgentStatus,
    AgentVersion,
    AgentVersioned,
    ModelRef,
)
from cora.agent.features.version_agent.command import VersionAgent
from cora.agent.features.version_agent.decider import decide

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)


def _defined_agent(*, agent_id: object | None = None) -> Agent:
    return Agent(
        id=agent_id or uuid4(),  # type: ignore[arg-type]
        kind=AgentKind("RunDebrief"),
        name=AgentName("Run Debrief"),
        version=AgentVersion("v1"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        status=AgentStatus.DEFINED,
    )


@pytest.mark.unit
def test_versions_a_defined_agent() -> None:
    agent = _defined_agent()
    events = decide(state=agent, command=VersionAgent(agent_id=agent.id), now=_NOW)
    assert len(events) == 1
    assert isinstance(events[0], AgentVersioned)
    assert events[0].agent_id == agent.id
    assert events[0].version == "v1"
    assert events[0].occurred_at == _NOW


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    with pytest.raises(AgentNotFoundError):
        decide(state=None, command=VersionAgent(agent_id=uuid4()), now=_NOW)


@pytest.mark.unit
def test_cannot_version_a_versioned_agent() -> None:
    agent = _defined_agent()
    versioned = Agent(
        id=agent.id,
        kind=agent.kind,
        name=agent.name,
        version=agent.version,
        model_ref=agent.model_ref,
        status=AgentStatus.VERSIONED,
    )
    with pytest.raises(AgentCannotVersionError):
        decide(state=versioned, command=VersionAgent(agent_id=versioned.id), now=_NOW)


@pytest.mark.unit
def test_cannot_version_a_deprecated_agent() -> None:
    agent = _defined_agent()
    deprecated = Agent(
        id=agent.id,
        kind=agent.kind,
        name=agent.name,
        version=agent.version,
        model_ref=agent.model_ref,
        status=AgentStatus.DEPRECATED,
    )
    with pytest.raises(AgentCannotVersionError):
        decide(state=deprecated, command=VersionAgent(agent_id=deprecated.id), now=_NOW)
