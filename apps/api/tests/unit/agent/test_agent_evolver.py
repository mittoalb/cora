"""Evolver tests for the Agent aggregate (Phase 8f-a)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cora.agent.aggregates.agent.events import (
    AgentDefined,
    AgentDeprecated,
    AgentVersioned,
)
from cora.agent.aggregates.agent.evolver import fold
from cora.agent.aggregates.agent.state import (
    AgentCapability,
    AgentStatus,
    ModelRef,
)

_T0 = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_T1 = _T0 + timedelta(minutes=10)
_T2 = _T0 + timedelta(minutes=20)


def _genesis(*, agent_id: object | None = None) -> AgentDefined:
    return AgentDefined(
        agent_id=agent_id or uuid4(),  # type: ignore[arg-type]
        kind="RunDebrief",
        name="Run Debrief",
        version="v1",
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        description="Synthesises terminal Runs.",
        canonical_uri="https://example.org/agents/run-debrief",
        prompt_template_id=None,
        capabilities=frozenset({"summarize"}),
        occurred_at=_T0,
    )


@pytest.mark.unit
def test_empty_stream_folds_to_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_genesis_folds_to_defined_state() -> None:
    e = _genesis()
    state = fold([e])
    assert state is not None
    assert state.id == e.agent_id
    assert state.status is AgentStatus.DEFINED
    assert state.kind.value == "RunDebrief"
    assert state.name.value == "Run Debrief"
    assert state.version.value == "v1"
    assert state.description is not None
    assert state.description.value == "Synthesises terminal Runs."
    assert state.canonical_uri is not None
    assert state.capabilities == frozenset({AgentCapability("summarize")})
    assert state.defined_at == _T0
    assert state.versioned_at is None
    assert state.deprecated_at is None


@pytest.mark.unit
def test_genesis_then_versioned_folds_to_versioned_state() -> None:
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentVersioned(agent_id=agent_id, version="v1", occurred_at=_T1)
    state = fold([e1, e2])
    assert state is not None
    assert state.status is AgentStatus.VERSIONED
    assert state.versioned_at == _T1
    # Other fields preserved.
    assert state.kind.value == "RunDebrief"
    assert state.defined_at == _T0


@pytest.mark.unit
def test_genesis_then_deprecated_folds_to_deprecated_state() -> None:
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentDeprecated(agent_id=agent_id, reason="model retired", occurred_at=_T1)
    state = fold([e1, e2])
    assert state is not None
    assert state.status is AgentStatus.DEPRECATED
    assert state.deprecated_at == _T1
    assert state.deprecation_reason is not None
    assert state.deprecation_reason.value == "model retired"


@pytest.mark.unit
def test_full_lifecycle_folds_to_deprecated_state() -> None:
    """Genesis -> Versioned -> Deprecated; all three transitions fold."""
    agent_id = uuid4()
    e1 = _genesis(agent_id=agent_id)
    e2 = AgentVersioned(agent_id=agent_id, version="v1", occurred_at=_T1)
    e3 = AgentDeprecated(agent_id=agent_id, reason=None, occurred_at=_T2)
    state = fold([e1, e2, e3])
    assert state is not None
    assert state.status is AgentStatus.DEPRECATED
    assert state.versioned_at == _T1
    assert state.deprecated_at == _T2
    assert state.deprecation_reason is None


@pytest.mark.unit
def test_versioned_applied_to_empty_state_raises() -> None:
    """The shared `require_state` helper raises on transition-before-genesis."""
    e = AgentVersioned(agent_id=uuid4(), version="v1", occurred_at=_T0)
    with pytest.raises(ValueError, match="AgentVersioned"):
        fold([e])


@pytest.mark.unit
def test_deprecated_applied_to_empty_state_raises() -> None:
    e = AgentDeprecated(agent_id=uuid4(), reason=None, occurred_at=_T0)
    with pytest.raises(ValueError, match="AgentDeprecated"):
        fold([e])
