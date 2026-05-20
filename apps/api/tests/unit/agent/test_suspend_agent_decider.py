"""Pure-decider tests for the `suspend_agent` slice (Phase 8f-c iter 2)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.agent.aggregates.agent import (
    AGENT_SUSPENSION_REASON_MAX_LENGTH,
    Agent,
    AgentCannotSuspendError,
    AgentKind,
    AgentName,
    AgentNotFoundError,
    AgentStatus,
    AgentSuspended,
    AgentVersion,
    InvalidAgentSuspensionReasonError,
    ModelRef,
)
from cora.agent.features.suspend_agent.command import SuspendAgent
from cora.agent.features.suspend_agent.decider import decide

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _agent(status: AgentStatus, *, agent_id: object | None = None) -> Agent:
    return Agent(
        id=agent_id or uuid4(),  # type: ignore[arg-type]
        kind=AgentKind("RunDebrief"),
        name=AgentName("Run Debrief"),
        version=AgentVersion("v1"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        status=status,
    )


@pytest.mark.unit
def test_suspends_a_versioned_agent() -> None:
    agent = _agent(AgentStatus.VERSIONED)
    events = decide(
        state=agent,
        command=SuspendAgent(agent_id=agent.id, reason="cost overrun"),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], AgentSuspended)
    assert events[0].reason == "cost overrun"
    assert events[0].occurred_at == _NOW


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    with pytest.raises(AgentNotFoundError):
        decide(
            state=None,
            command=SuspendAgent(agent_id=uuid4(), reason="x"),
            now=_NOW,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "status", [AgentStatus.DEFINED, AgentStatus.SUSPENDED, AgentStatus.DEPRECATED]
)
def test_cannot_suspend_from_non_versioned(status: AgentStatus) -> None:
    agent = _agent(status)
    with pytest.raises(AgentCannotSuspendError):
        decide(
            state=agent,
            command=SuspendAgent(agent_id=agent.id, reason="x"),
            now=_NOW,
        )


@pytest.mark.unit
def test_reason_trims_via_value_object() -> None:
    agent = _agent(AgentStatus.VERSIONED)
    events = decide(
        state=agent,
        command=SuspendAgent(agent_id=agent.id, reason="  output regression  "),
        now=_NOW,
    )
    assert events[0].reason == "output regression"


@pytest.mark.unit
def test_reason_empty_raises() -> None:
    agent = _agent(AgentStatus.VERSIONED)
    with pytest.raises(InvalidAgentSuspensionReasonError):
        decide(
            state=agent,
            command=SuspendAgent(agent_id=agent.id, reason="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_reason_over_cap_raises() -> None:
    agent = _agent(AgentStatus.VERSIONED)
    with pytest.raises(InvalidAgentSuspensionReasonError):
        decide(
            state=agent,
            command=SuspendAgent(
                agent_id=agent.id,
                reason="x" * (AGENT_SUSPENSION_REASON_MAX_LENGTH + 1),
            ),
            now=_NOW,
        )
