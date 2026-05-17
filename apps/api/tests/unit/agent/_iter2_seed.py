"""Shared seed helpers for the Phase 8f-c iter 2 handler tests.

Each new transition slice's handler test (suspend / resume / grant /
revoke / revise-budget) needs to seed a `Versioned` or `Suspended`
or `Defined` Agent against an InMemoryEventStore. The helpers keep
per-test files focused on assertions rather than re-encoding the
same seed dance.
"""

from datetime import datetime
from uuid import UUID

from cora.agent.aggregates.agent import (
    AgentDefined,
    AgentResumed,
    AgentSuspended,
    AgentToolGranted,
    AgentVersioned,
    ModelRef,
    event_type_name,
    to_payload,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.memory.event_store import InMemoryEventStore


async def seed_defined_agent(
    store: InMemoryEventStore,
    *,
    agent_id: UUID,
    genesis_event_id: UUID,
    correlation_id: UUID,
    principal_id: UUID,
    occurred_at: datetime,
) -> None:
    """Append a single `AgentDefined` event to a fresh Agent stream."""
    genesis = AgentDefined(
        agent_id=agent_id,
        kind="RunDebrief",
        name="Run Debrief",
        version="v1",
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        description=None,
        canonical_uri=None,
        prompt_template_id=None,
        capabilities=frozenset(),
        occurred_at=occurred_at,
    )
    await store.append(
        stream_type="Agent",
        stream_id=agent_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(genesis),
                payload=to_payload(genesis),
                occurred_at=genesis.occurred_at,
                event_id=genesis_event_id,
                command_name="DefineAgent",
                correlation_id=correlation_id,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )


async def seed_versioned_agent(
    store: InMemoryEventStore,
    *,
    agent_id: UUID,
    genesis_event_id: UUID,
    version_event_id: UUID,
    correlation_id: UUID,
    principal_id: UUID,
    defined_at: datetime,
    versioned_at: datetime,
) -> None:
    """Seed Defined then Versioned, leaving the Agent at stream version 2."""
    await seed_defined_agent(
        store,
        agent_id=agent_id,
        genesis_event_id=genesis_event_id,
        correlation_id=correlation_id,
        principal_id=principal_id,
        occurred_at=defined_at,
    )
    versioned = AgentVersioned(agent_id=agent_id, version="v1", occurred_at=versioned_at)
    await store.append(
        stream_type="Agent",
        stream_id=agent_id,
        expected_version=1,
        events=[
            to_new_event(
                event_type=event_type_name(versioned),
                payload=to_payload(versioned),
                occurred_at=versioned.occurred_at,
                event_id=version_event_id,
                command_name="VersionAgent",
                correlation_id=correlation_id,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )


async def seed_suspended_agent(
    store: InMemoryEventStore,
    *,
    agent_id: UUID,
    genesis_event_id: UUID,
    version_event_id: UUID,
    suspend_event_id: UUID,
    correlation_id: UUID,
    principal_id: UUID,
    defined_at: datetime,
    versioned_at: datetime,
    suspended_at: datetime,
    reason: str = "operator pause",
) -> None:
    """Seed Defined then Versioned then Suspended, ending at stream version 3."""
    await seed_versioned_agent(
        store,
        agent_id=agent_id,
        genesis_event_id=genesis_event_id,
        version_event_id=version_event_id,
        correlation_id=correlation_id,
        principal_id=principal_id,
        defined_at=defined_at,
        versioned_at=versioned_at,
    )
    suspended = AgentSuspended(agent_id=agent_id, reason=reason, occurred_at=suspended_at)
    await store.append(
        stream_type="Agent",
        stream_id=agent_id,
        expected_version=2,
        events=[
            to_new_event(
                event_type=event_type_name(suspended),
                payload=to_payload(suspended),
                occurred_at=suspended.occurred_at,
                event_id=suspend_event_id,
                command_name="SuspendAgent",
                correlation_id=correlation_id,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )


async def append_tool_grant(
    store: InMemoryEventStore,
    *,
    agent_id: UUID,
    expected_version: int,
    event_id: UUID,
    correlation_id: UUID,
    principal_id: UUID,
    tool_name: str,
    occurred_at: datetime,
) -> None:
    """Append a single AgentToolGranted event at the given expected_version."""
    granted = AgentToolGranted(agent_id=agent_id, tool_name=tool_name, occurred_at=occurred_at)
    await store.append(
        stream_type="Agent",
        stream_id=agent_id,
        expected_version=expected_version,
        events=[
            to_new_event(
                event_type=event_type_name(granted),
                payload=to_payload(granted),
                occurred_at=granted.occurred_at,
                event_id=event_id,
                command_name="GrantToolToAgent",
                correlation_id=correlation_id,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )


async def append_resume(
    store: InMemoryEventStore,
    *,
    agent_id: UUID,
    expected_version: int,
    event_id: UUID,
    correlation_id: UUID,
    principal_id: UUID,
    occurred_at: datetime,
) -> None:
    """Append a single AgentResumed event."""
    resumed = AgentResumed(agent_id=agent_id, occurred_at=occurred_at)
    await store.append(
        stream_type="Agent",
        stream_id=agent_id,
        expected_version=expected_version,
        events=[
            to_new_event(
                event_type=event_type_name(resumed),
                payload=to_payload(resumed),
                occurred_at=resumed.occurred_at,
                event_id=event_id,
                command_name="ResumeAgent",
                correlation_id=correlation_id,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )
