"""End-to-end PG integration for the RunDebriefer subscriber.

Walks: seed RunDebriefer Agent + Actor -> start a Run -> emit a
terminal Run event -> invoke the subscriber -> verify a
`DecisionRegistered` lands in proj_decision_summary with the
expected RunDebrief shape.

Uses `FakeLLM` for the LLM call (no Anthropic API key
needed in CI). Real-Anthropic recorded-cassette test is a watch
item for later iters.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingParameterType=false, reportPrivateUsage=false, reportUnknownParameterType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.access.aggregates.actor import (
    ActorKind,
    ActorRegistered,
)
from cora.access.aggregates.actor import event_type_name as actor_event_type_name
from cora.access.aggregates.actor import to_payload as actor_to_payload
from cora.agent.seed import (
    RUN_DEBRIEFER_AGENT_ID,
    seed_run_debriefer_agent,
)
from cora.agent.subscribers.run_debriefer import (
    RunDebrieferSubscriber,
    _derive_decision_id,
)
from cora.decision.aggregates.decision import load_decision
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import FakeLLM, FakeLLMResponse
from cora.infrastructure.ports.event_store import StoredEvent
from cora.run.aggregates.run import RunStarted
from cora.run.aggregates.run import event_type_name as run_event_type_name
from cora.run.aggregates.run import to_payload as run_to_payload
from cora.run.aggregates.run.events import RunCompleted
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 17, 14, 47, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000099001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000009900a")


async def _seed_run(deps, run_id: UUID, plan_id: UUID) -> None:
    started = RunStarted(
        run_id=run_id,
        name="PG Integration Test Run",
        plan_id=plan_id,
        subject_id=None,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=run_event_type_name(started),
        payload=run_to_payload(started),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await deps.event_store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=0,
        events=[new_event],
    )


def _terminal_event(run_id: UUID) -> StoredEvent:
    domain = RunCompleted(run_id=run_id, occurred_at=_LATER)
    return StoredEvent(
        position=1,
        event_id=UUID("01900000-0000-7000-8000-00000000fe01"),
        stream_type="Run",
        stream_id=run_id,
        version=2,
        event_type="RunCompleted",
        schema_version=1,
        payload=run_to_payload(domain),
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_LATER,
        recorded_at=_LATER,
    )


_CANNED_OK = FakeLLMResponse(
    parsed={
        "choice": "NominalCompletion",
        "confidence": 0.91,
        "reasoning": (
            "PG integration smoke test: Run completed cleanly. "
            "Synopsis: a single-Plan Run on the bound Subject ran to "
            "RunCompleted in 47 minutes. What was supposed to happen: "
            "complete the planned scan. What actually happened: "
            "RunCompleted with zero adjustments. Why the difference: "
            "no difference; nominal execution."
        ),
    },
    stop_reason="tool_use",
    model_id="claude-haiku-4-5",
)


@pytest.mark.integration
async def test_seed_and_subscriber_write_decision_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW)

    # Bootstrap: seed RunDebriefer Agent + Actor.
    await seed_run_debriefer_agent(deps)
    # Second call must be a no-op (idempotent on real PG).
    await seed_run_debriefer_agent(deps)

    # Seed a Run.
    run_id = uuid4()
    plan_id = UUID("01900000-0000-7000-8000-000000000401")
    await _seed_run(deps, run_id, plan_id)

    # Build the subscriber + invoke apply() against a terminal event.
    llm = FakeLLM(responses=[_CANNED_OK])
    subscriber = RunDebrieferSubscriber(
        event_store=deps.event_store,
        llm=llm,
        logbook_mirror=None,
    )
    event = _terminal_event(run_id)

    await subscriber.apply(event, conn=None)

    # Decision landed on the Decision stream with the deterministic id.
    decision_id = _derive_decision_id(event.event_id)
    decision = await load_decision(deps.event_store, decision_id)
    assert decision is not None
    assert decision.context.value == "RunDebrief"
    assert decision.choice.value == "NominalCompletion"
    assert decision.actor_id == RUN_DEBRIEFER_AGENT_ID

    # LLM was called exactly once; payload contained the run_id.
    assert len(llm.received) == 1
    assert str(run_id) in llm.received[0].user_message.text


@pytest.mark.integration
async def test_subscriber_retry_is_at_most_once_on_real_pg(
    db_pool: asyncpg.Pool,
) -> None:
    """Two apply() calls with the same terminal event produce ONE
    Decision on PG (ConcurrencyError on second write is caught and
    treated as no-op)."""
    deps = build_postgres_deps(db_pool, now=_NOW)
    await seed_run_debriefer_agent(deps)

    run_id = uuid4()
    plan_id = UUID("01900000-0000-7000-8000-000000000401")
    await _seed_run(deps, run_id, plan_id)

    llm = FakeLLM(responses=[_CANNED_OK, _CANNED_OK])
    subscriber = RunDebrieferSubscriber(
        event_store=deps.event_store,
        llm=llm,
        logbook_mirror=None,
    )
    event = _terminal_event(run_id)

    await subscriber.apply(event, conn=None)
    # Second apply: the deterministic decision_id collides with the
    # already-written stream; ConcurrencyError is caught and treated
    # as success.
    await subscriber.apply(event, conn=None)

    # Decision stream still at version 1; no duplicate event.
    decision_id = _derive_decision_id(event.event_id)
    events_list, version = await deps.event_store.load("Decision", decision_id)
    assert version == 1
    assert len(events_list) == 1


@pytest.mark.integration
async def test_seed_does_not_collide_with_pre_existing_actor(
    db_pool: asyncpg.Pool,
) -> None:
    """If someone manually seeded an Actor at RUN_DEBRIEFER_AGENT_ID
    before the bootstrap ran, seed_run_debriefer_agent should still
    not raise (ConcurrencyError caught). Demonstrates partial-state
    recovery."""
    deps = build_postgres_deps(db_pool, now=_NOW)

    # Manually seed JUST the Actor (no Agent record).
    actor_event = ActorRegistered(
        actor_id=RUN_DEBRIEFER_AGENT_ID,
        occurred_at=_NOW,
        kind=ActorKind.AGENT,
    )
    new_event = to_new_event(
        event_type=actor_event_type_name(actor_event),
        payload=actor_to_payload(actor_event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="ManualSeed",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await deps.event_store.append(
        stream_type="Actor",
        stream_id=RUN_DEBRIEFER_AGENT_ID,
        expected_version=0,
        events=[new_event],
    )

    # Now the seed runs. The Actor stream collides (rolls back the
    # whole append_streams batch), seed returns cleanly.
    await seed_run_debriefer_agent(deps)

    # Agent stream never got written (the whole batch rolled back).
    # This is a documented edge case; future iteration can split the
    # writes for finer-grained recovery, but the current design accepts
    # the all-or-nothing semantics of append_streams.
    _, agent_version = await deps.event_store.load("Agent", RUN_DEBRIEFER_AGENT_ID)
    assert agent_version == 0  # Agent stream is empty (batch rolled back)
