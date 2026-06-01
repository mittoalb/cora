"""Pure-decider tests for the `grant_tool_to_agent` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.agent.aggregates.agent import (
    AGENT_TOOL_NAME_MAX_LENGTH,
    AGENT_TOOLS_MAX_COUNT,
    Agent,
    AgentCannotGrantToolError,
    AgentKind,
    AgentName,
    AgentNotFoundError,
    AgentStatus,
    AgentToolGranted,
    AgentVersion,
    InvalidAgentToolsError,
    InvalidToolNameError,
    ModelRef,
    ToolName,
)
from cora.agent.features.grant_tool_to_agent.command import GrantToolToAgent
from cora.agent.features.grant_tool_to_agent.decider import decide

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _agent(
    status: AgentStatus,
    *,
    tools: frozenset[ToolName] = frozenset(),
    agent_id: object | None = None,
) -> Agent:
    return Agent(
        id=agent_id or uuid4(),  # type: ignore[arg-type]
        kind=AgentKind("RunDebriefer"),
        name=AgentName("Run Debrief"),
        version=AgentVersion("v1"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        status=status,
        tools=tools,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "status", [AgentStatus.DEFINED, AgentStatus.VERSIONED, AgentStatus.SUSPENDED]
)
def test_grants_a_new_tool_in_each_allowed_source_state(status: AgentStatus) -> None:
    agent = _agent(status)
    events = decide(
        state=agent,
        command=GrantToolToAgent(agent_id=agent.id, tool_name="read_run"),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], AgentToolGranted)
    assert events[0].tool_name == "read_run"


@pytest.mark.unit
def test_idempotent_re_grant_emits_no_event() -> None:
    agent = _agent(AgentStatus.VERSIONED, tools=frozenset({ToolName("read_run")}))
    events = decide(
        state=agent,
        command=GrantToolToAgent(agent_id=agent.id, tool_name="read_run"),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_idempotent_re_grant_uses_trimmed_form_for_comparison() -> None:
    agent = _agent(AgentStatus.VERSIONED, tools=frozenset({ToolName("read_run")}))
    events = decide(
        state=agent,
        command=GrantToolToAgent(agent_id=agent.id, tool_name="  read_run  "),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    with pytest.raises(AgentNotFoundError):
        decide(
            state=None,
            command=GrantToolToAgent(agent_id=uuid4(), tool_name="read_run"),
            now=_NOW,
        )


@pytest.mark.unit
def test_cannot_grant_when_deprecated() -> None:
    agent = _agent(AgentStatus.DEPRECATED)
    with pytest.raises(AgentCannotGrantToolError):
        decide(
            state=agent,
            command=GrantToolToAgent(agent_id=agent.id, tool_name="read_run"),
            now=_NOW,
        )


@pytest.mark.unit
def test_invalid_tool_name_raises() -> None:
    agent = _agent(AgentStatus.VERSIONED)
    with pytest.raises(InvalidToolNameError):
        decide(
            state=agent,
            command=GrantToolToAgent(agent_id=agent.id, tool_name="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_tool_name_over_cap_raises() -> None:
    agent = _agent(AgentStatus.VERSIONED)
    with pytest.raises(InvalidToolNameError):
        decide(
            state=agent,
            command=GrantToolToAgent(
                agent_id=agent.id,
                tool_name="x" * (AGENT_TOOL_NAME_MAX_LENGTH + 1),
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_grant_at_cap_with_existing_tool_is_still_idempotent() -> None:
    """A re-grant of an already-granted tool against a full set succeeds silently.

    The cardinality cap is enforced only when the grant would actually
    add a new entry.
    """
    full = frozenset(ToolName(f"tool_{i}") for i in range(AGENT_TOOLS_MAX_COUNT))
    agent = _agent(AgentStatus.VERSIONED, tools=full)
    events = decide(
        state=agent,
        command=GrantToolToAgent(agent_id=agent.id, tool_name="tool_0"),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_grant_that_would_exceed_cardinality_cap_raises() -> None:
    full = frozenset(ToolName(f"tool_{i}") for i in range(AGENT_TOOLS_MAX_COUNT))
    agent = _agent(AgentStatus.VERSIONED, tools=full)
    with pytest.raises(InvalidAgentToolsError):
        decide(
            state=agent,
            command=GrantToolToAgent(agent_id=agent.id, tool_name="overflow"),
            now=_NOW,
        )
