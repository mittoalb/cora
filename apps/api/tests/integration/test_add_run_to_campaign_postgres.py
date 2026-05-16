"""End-to-end PG integration test: `add_run_to_campaign` two-stream atomic write.

Pins the cross-aggregate, multi-stream atomic-write contract under
real Postgres for Phase 6i-c:

  1. Happy-path round-trip: Campaign gains run_id in its run_ids;
     Run gains campaign_id on its state. Both stream version cursors
     advance in a single transaction (shared xid8).
  2. Projection denorm: proj_recipe_campaign_summary.run_count is
     bumped after the worker drains.

Seeds Run state directly via event-store appends to avoid pulling
the full upstream Plan / Practice / Method / Asset / Subject chain
into this test (the Run aggregate's membership invariants don't
depend on that chain; the start_run upstream chain has its own
integration test at test_start_run_handler_postgres.py).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingParameterType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.campaign._projections import register_campaign_projections
from cora.campaign.aggregates.campaign import (
    CampaignIntent,
)
from cora.campaign.aggregates.campaign import (
    fold as campaign_fold,
)
from cora.campaign.aggregates.campaign import (
    from_stored as campaign_from_stored,
)
from cora.campaign.features import add_run_to_campaign, register_campaign, start_campaign
from cora.campaign.features.add_run_to_campaign import AddRunToCampaign
from cora.campaign.features.register_campaign import RegisterCampaign
from cora.campaign.features.start_campaign import StartCampaign
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.run.aggregates.run import (
    event_type_name as run_event_type_name,
)
from cora.run.aggregates.run import (
    fold as run_fold,
)
from cora.run.aggregates.run import (
    from_stored as run_from_stored,
)
from cora.run.aggregates.run import (
    to_payload as run_to_payload,
)
from cora.run.aggregates.run.events import RunStarted
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_run_via_event_store(
    deps, run_id: UUID, *, event_id: UUID, principal_id: UUID = _PRINCIPAL_ID
) -> None:
    """Append a RunStarted event directly to the Run stream."""
    event = RunStarted(
        run_id=run_id,
        name="member-run",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
    )
    await deps.event_store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=run_event_type_name(event),
                payload=run_to_payload(event),
                occurred_at=event.occurred_at,
                event_id=event_id,
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_campaign_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_add_run_to_campaign_writes_both_streams_atomically(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy-path: Run + Campaign exist standalone; add_run_to_campaign
    writes CampaignRunAdded on Campaign + RunCampaignAssigned on Run
    via append_streams; both streams reflect the membership."""
    campaign_id = uuid4()
    register_event_id = uuid4()
    start_event_id = uuid4()
    run_id = uuid4()
    add_campaign_event_id = uuid4()
    add_run_event_id = uuid4()
    lead = uuid4()

    # IDs consumed in order by the kernel's FixedIdGenerator:
    #   register_campaign: campaign_id + register_event_id (2)
    #   start_campaign:    start_event_id (1)
    #   add_run_to_campaign: add_campaign_event_id + add_run_event_id (2)
    # The Run seed uses a separately-allocated uuid4 (does not pull
    # from the queue) -- the helper passes it directly.
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            campaign_id,
            register_event_id,
            start_event_id,
            add_campaign_event_id,
            add_run_event_id,
        ],
    )

    # Register + Start Campaign.
    await register_campaign.bind(deps)(
        RegisterCampaign(
            name="test campaign",
            intent=CampaignIntent.IN_SITU,
            lead_actor_id=lead,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await start_campaign.bind(deps)(
        StartCampaign(campaign_id=campaign_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Seed a Run directly via event-store append.
    await _seed_run_via_event_store(deps, run_id, event_id=uuid4())

    # Add Run to Campaign.
    await add_run_to_campaign.bind(deps)(
        AddRunToCampaign(campaign_id=campaign_id, run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Campaign stream: 3 events (Registered + Started + RunAdded).
    campaign_events, campaign_version = await deps.event_store.load("Campaign", campaign_id)
    assert campaign_version == 3
    assert campaign_events[-1].event_type == "CampaignRunAdded"
    assert campaign_events[-1].payload["run_id"] == str(run_id)
    state = campaign_fold([campaign_from_stored(s) for s in campaign_events])
    assert state is not None
    assert run_id in state.run_ids

    # Run stream: 2 events (Started + CampaignAssigned).
    run_events, run_version = await deps.event_store.load("Run", run_id)
    assert run_version == 2
    assert run_events[-1].event_type == "RunCampaignAssigned"
    assert run_events[-1].payload["campaign_id"] == str(campaign_id)
    run_state = run_fold([run_from_stored(s) for s in run_events])
    assert run_state is not None
    assert run_state.campaign_id == campaign_id

    # Atomic xid8 invariant: Campaign's CampaignRunAdded + Run's
    # RunCampaignAssigned share the same transaction_id.
    assert campaign_events[-1].transaction_id == run_events[-1].transaction_id


@pytest.mark.integration
async def test_add_run_to_campaign_bumps_run_count_after_drain(
    db_pool: asyncpg.Pool,
) -> None:
    """Projection: after add_run + drain, proj_recipe_campaign_summary
    has run_count=1 for the Campaign."""
    campaign_id = uuid4()
    run_id = uuid4()
    lead = uuid4()

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[campaign_id] + [uuid4() for _ in range(6)],
    )

    await register_campaign.bind(deps)(
        RegisterCampaign(
            name="run-count test",
            intent=CampaignIntent.OPERANDO,
            lead_actor_id=lead,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await start_campaign.bind(deps)(
        StartCampaign(campaign_id=campaign_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _seed_run_via_event_store(deps, run_id, event_id=uuid4())
    await add_run_to_campaign.bind(deps)(
        AddRunToCampaign(campaign_id=campaign_id, run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT run_count FROM proj_recipe_campaign_summary WHERE campaign_id = $1",
            campaign_id,
        )
    assert row is not None
    assert row["run_count"] == 1
