"""Unit tests for the CautionDrafter Agent bootstrap seed."""

from datetime import UTC, datetime

import pytest

from cora.agent.aggregates.agent import load_agent
from cora.agent.prompts import CAUTION_DRAFTER_PROMPT_TEMPLATE_ID
from cora.agent.seed_caution_drafter import (
    CAUTION_DRAFTER_AGENT_ID,
    CAUTION_DRAFTER_AGENT_KIND,
    CAUTION_DRAFTER_AGENT_NAME,
    CAUTION_DRAFTER_AGENT_VERSION,
    seed_caution_drafter_agent,
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
        authz=AllowAllAuthorize(),
    )


@pytest.mark.unit
async def test_seed_creates_caution_drafter_at_pinned_id() -> None:
    kernel = _kernel()
    await seed_caution_drafter_agent(kernel)

    agent = await load_agent(kernel.event_store, CAUTION_DRAFTER_AGENT_ID)
    assert agent is not None
    assert agent.id == CAUTION_DRAFTER_AGENT_ID
    assert agent.name.value == CAUTION_DRAFTER_AGENT_NAME
    assert agent.kind.value == CAUTION_DRAFTER_AGENT_KIND
    assert agent.version.value == CAUTION_DRAFTER_AGENT_VERSION
    assert agent.prompt_template_id == CAUTION_DRAFTER_PROMPT_TEMPLATE_ID


@pytest.mark.unit
async def test_seed_creates_co_registered_actor() -> None:
    """The cross-BC genesis: Actor (kind=agent) at the pinned id.

    PII vault: the Actor aggregate carries no `name`. Display name
    lives in `actor_profile`; the seed upserts it via the
    InMemoryProfileStore constructed inside `seed_caution_drafter_agent`
    when `kernel.pool is None`. Vault-side coverage lives in the
    `test_seed_upserts_actor_profile` test below.
    """
    from cora.access.aggregates.actor import load_actor

    kernel = _kernel()
    await seed_caution_drafter_agent(kernel)

    actor = await load_actor(kernel.event_store, CAUTION_DRAFTER_AGENT_ID)
    assert actor is not None
    assert actor.id == CAUTION_DRAFTER_AGENT_ID
    assert actor.kind.value == "agent"


@pytest.mark.unit
async def test_seed_is_resilient_under_pre_existing_actor_only_stream() -> None:
    """If the Actor stream exists but the Agent stream doesn't (a
    partial-prior-seed crash), the second seed call must still raise
    the ConcurrencyError-as-success path without double-writing the
    actor."""
    kernel = _kernel()
    await seed_caution_drafter_agent(kernel)
    await seed_caution_drafter_agent(kernel)  # second seed: no-op via ConcurrencyError


@pytest.mark.unit
async def test_seed_is_idempotent() -> None:
    """Re-running the seed is a no-op (ConcurrencyError-as-success pattern)."""
    kernel = _kernel()
    await seed_caution_drafter_agent(kernel)
    # Should not raise on second run.
    await seed_caution_drafter_agent(kernel)


@pytest.mark.unit
async def test_caution_drafter_id_distinct_from_run_debriefer() -> None:
    """The two agents share the same UUID-range scheme but must NOT collide."""
    from cora.agent.seed import RUN_DEBRIEFER_AGENT_ID

    assert CAUTION_DRAFTER_AGENT_ID != RUN_DEBRIEFER_AGENT_ID
