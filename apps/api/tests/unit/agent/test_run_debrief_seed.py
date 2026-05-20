"""Unit tests for the RunDebrief Agent bootstrap seed (Phase 8f-b iter 2b)."""

from datetime import UTC, datetime

import pytest

from cora.agent.aggregates.agent import load_agent
from cora.agent.prompts import RUN_DEBRIEF_PROMPT_TEMPLATE_ID
from cora.agent.seed import (
    RUN_DEBRIEF_AGENT_ID,
    RUN_DEBRIEF_AGENT_KIND,
    RUN_DEBRIEF_AGENT_NAME,
    RUN_DEBRIEF_AGENT_VERSION,
    seed_run_debrief_agent,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, FixedIdGenerator


def _kernel() -> Kernel:
    settings = Settings()  # type: ignore[call-arg]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)),
        id_generator=FixedIdGenerator([]),
        authorize=AllowAllAuthorize(),
    )


@pytest.mark.unit
async def test_seed_creates_agent_at_pinned_id() -> None:
    kernel = _kernel()
    await seed_run_debrief_agent(kernel)

    agent = await load_agent(kernel.event_store, RUN_DEBRIEF_AGENT_ID)
    assert agent is not None
    assert agent.id == RUN_DEBRIEF_AGENT_ID
    assert agent.name.value == RUN_DEBRIEF_AGENT_NAME
    assert agent.kind.value == RUN_DEBRIEF_AGENT_KIND
    assert agent.version.value == RUN_DEBRIEF_AGENT_VERSION
    assert agent.prompt_template_id == RUN_DEBRIEF_PROMPT_TEMPLATE_ID


@pytest.mark.unit
async def test_seed_creates_co_registered_actor() -> None:
    """The Agent's id is SHARED with Access BC's Actor.id per 8f-a's
    identity-sharing invariant. The seed writes both atomically."""
    from cora.access.aggregates.actor import load_actor

    kernel = _kernel()
    await seed_run_debrief_agent(kernel)

    actor = await load_actor(kernel.event_store, RUN_DEBRIEF_AGENT_ID)
    assert actor is not None
    assert actor.id == RUN_DEBRIEF_AGENT_ID
    assert actor.kind.value == "agent"


@pytest.mark.unit
async def test_seed_is_idempotent_across_calls() -> None:
    """A repeated seed call (on every app boot) MUST NOT raise and
    MUST NOT duplicate the agent. Pins the
    ConcurrencyError-as-no-op semantics."""
    kernel = _kernel()
    await seed_run_debrief_agent(kernel)
    # Second call must not raise.
    await seed_run_debrief_agent(kernel)
    # Third call for good measure.
    await seed_run_debrief_agent(kernel)

    # Still exactly one agent at the pinned id.
    agent = await load_agent(kernel.event_store, RUN_DEBRIEF_AGENT_ID)
    assert agent is not None
    # Stream version is still 1 (one event), not 3.
    events, version = await kernel.event_store.load("Agent", RUN_DEBRIEF_AGENT_ID)
    assert version == 1
    assert len(events) == 1


@pytest.mark.unit
async def test_seed_pins_prompt_template_id() -> None:
    """The bootstrap stores the prompt_template_id so the subscriber
    can record it in `Decision.decision_inputs["prompt_template_id"]`
    for audit. Pin the linkage so a misnumbered template would
    surface here."""
    kernel = _kernel()
    await seed_run_debrief_agent(kernel)

    agent = await load_agent(kernel.event_store, RUN_DEBRIEF_AGENT_ID)
    assert agent is not None
    assert agent.prompt_template_id == RUN_DEBRIEF_PROMPT_TEMPLATE_ID


@pytest.mark.unit
async def test_seed_uses_system_principal_id_not_agent_self_reference() -> None:
    """Security gate-review P1#3: the bootstrap envelope's
    `principal_id` must be `SYSTEM_PRINCIPAL_ID`, NOT the agent's
    own id. The agent doesn't exist yet at boot-time, so self-
    attribution would be a circular-causation lie in the audit
    record."""
    from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

    kernel = _kernel()
    await seed_run_debrief_agent(kernel)

    actor_events, _ = await kernel.event_store.load("Actor", RUN_DEBRIEF_AGENT_ID)
    assert len(actor_events) == 1
    assert actor_events[0].principal_id == SYSTEM_PRINCIPAL_ID
    assert actor_events[0].principal_id != RUN_DEBRIEF_AGENT_ID

    agent_events, _ = await kernel.event_store.load("Agent", RUN_DEBRIEF_AGENT_ID)
    assert len(agent_events) == 1
    assert agent_events[0].principal_id == SYSTEM_PRINCIPAL_ID
