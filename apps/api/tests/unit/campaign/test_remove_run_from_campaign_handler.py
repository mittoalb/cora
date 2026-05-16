"""Application-handler tests for `remove_run_from_campaign` slice.

Pre-load both streams, decide, write both atomically. Phase 6i-c.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.campaign.aggregates.campaign import (
    CampaignNotFoundError,
    CampaignRegistered,
    CampaignRunNotMemberError,
    CampaignStarted,
)
from cora.campaign.aggregates.campaign import (
    event_type_name as campaign_event_type_name,
)
from cora.campaign.aggregates.campaign import (
    fold as campaign_fold,
)
from cora.campaign.aggregates.campaign import (
    from_stored as campaign_from_stored,
)
from cora.campaign.aggregates.campaign import (
    to_payload as campaign_to_payload,
)
from cora.campaign.features import add_run_to_campaign, remove_run_from_campaign
from cora.campaign.features.add_run_to_campaign import AddRunToCampaign
from cora.campaign.features.remove_run_from_campaign import RemoveRunFromCampaign
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.run.aggregates.run import (
    RunNotFoundError,
    RunStarted,
)
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
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 17, 15, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000ff0001")
_RUN_ID = UUID("01900000-0000-7000-8000-000000ff0002")
_LEAD = UUID("01900000-0000-7000-8000-000000ff00aa")
_PLAN = UUID("01900000-0000-7000-8000-000000ff00bb")
_PRINCIPAL = UUID("01900000-0000-7000-8000-000000ff0099")
_CORRELATION = UUID("01900000-0000-7000-8000-000000ff00cc")


async def _seed_campaign_active(store: InMemoryEventStore) -> None:
    for idx, event in enumerate(
        [
            CampaignRegistered(
                campaign_id=_CAMPAIGN_ID,
                name="campaign",
                intent="InSitu",
                lead_actor_id=_LEAD,
                subject_id=None,
                description=None,
                tags=frozenset(),
                external_refs=frozenset(),
                external_id=None,
                occurred_at=_PRIOR,
            ),
            CampaignStarted(campaign_id=_CAMPAIGN_ID, occurred_at=_PRIOR),
        ]
    ):
        await store.append(
            stream_type="Campaign",
            stream_id=_CAMPAIGN_ID,
            expected_version=idx,
            events=[
                to_new_event(
                    event_type=campaign_event_type_name(event),
                    payload=campaign_to_payload(event),
                    occurred_at=event.occurred_at,
                    event_id=uuid4(),
                    command_name="seed",
                    correlation_id=_CORRELATION,
                    causation_id=None,
                    principal_id=_PRINCIPAL,
                )
            ],
        )


async def _seed_run(store: InMemoryEventStore) -> None:
    event = RunStarted(
        run_id=_RUN_ID,
        name="standalone",
        plan_id=_PLAN,
        subject_id=None,
        occurred_at=_PRIOR,
    )
    await store.append(
        stream_type="Run",
        stream_id=_RUN_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=run_event_type_name(event),
                payload=run_to_payload(event),
                occurred_at=event.occurred_at,
                event_id=uuid4(),
                command_name="seed",
                correlation_id=_CORRELATION,
                causation_id=None,
                principal_id=_PRINCIPAL,
            )
        ],
    )


async def _seed_run_in_campaign(store: InMemoryEventStore) -> None:
    """Seed Campaign + Run + add Run to Campaign via the add slice."""
    await _seed_campaign_active(store)
    await _seed_run(store)
    deps = build_deps(
        now=_PRIOR,
        event_store=store,
        ids=[uuid4() for _ in range(4)],
    )
    add_handler = add_run_to_campaign.bind(deps)
    await add_handler(
        AddRunToCampaign(campaign_id=_CAMPAIGN_ID, run_id=_RUN_ID),
        principal_id=_PRINCIPAL,
        correlation_id=_CORRELATION,
    )


@pytest.mark.unit
async def test_handler_removes_run_from_both_streams_atomically() -> None:
    store = InMemoryEventStore()
    await _seed_run_in_campaign(store)

    deps = build_deps(
        now=_NOW,
        event_store=store,
        ids=[uuid4() for _ in range(4)],
    )
    handler = remove_run_from_campaign.bind(deps)
    await handler(
        RemoveRunFromCampaign(
            campaign_id=_CAMPAIGN_ID,
            run_id=_RUN_ID,
            reason="follow-on study",
        ),
        principal_id=_PRINCIPAL,
        correlation_id=_CORRELATION,
    )

    campaign_stored, _ = await store.load("Campaign", _CAMPAIGN_ID)
    campaign_state = campaign_fold([campaign_from_stored(s) for s in campaign_stored])
    assert campaign_state is not None
    assert _RUN_ID not in campaign_state.run_ids

    run_stored, _ = await store.load("Run", _RUN_ID)
    run_state = run_fold([run_from_stored(s) for s in run_stored])
    assert run_state is not None
    assert run_state.campaign_id is None


@pytest.mark.unit
async def test_handler_raises_campaign_not_found_when_missing() -> None:
    store = InMemoryEventStore()
    await _seed_run(store)
    deps = build_deps(now=_NOW, event_store=store, ids=[uuid4(), uuid4()])
    handler = remove_run_from_campaign.bind(deps)
    with pytest.raises(CampaignNotFoundError):
        await handler(
            RemoveRunFromCampaign(
                campaign_id=_CAMPAIGN_ID,
                run_id=_RUN_ID,
                reason="x",
            ),
            principal_id=_PRINCIPAL,
            correlation_id=_CORRELATION,
        )


@pytest.mark.unit
async def test_handler_raises_run_not_found_when_missing() -> None:
    store = InMemoryEventStore()
    await _seed_campaign_active(store)
    deps = build_deps(now=_NOW, event_store=store, ids=[uuid4(), uuid4()])
    handler = remove_run_from_campaign.bind(deps)
    with pytest.raises(RunNotFoundError):
        await handler(
            RemoveRunFromCampaign(
                campaign_id=_CAMPAIGN_ID,
                run_id=_RUN_ID,
                reason="x",
            ),
            principal_id=_PRINCIPAL,
            correlation_id=_CORRELATION,
        )


@pytest.mark.unit
async def test_handler_raises_not_member_when_run_not_in_run_ids() -> None:
    """Run exists but was never added to the Campaign."""
    store = InMemoryEventStore()
    await _seed_campaign_active(store)
    await _seed_run(store)
    deps = build_deps(now=_NOW, event_store=store, ids=[uuid4(), uuid4()])
    handler = remove_run_from_campaign.bind(deps)
    with pytest.raises(CampaignRunNotMemberError):
        await handler(
            RemoveRunFromCampaign(
                campaign_id=_CAMPAIGN_ID,
                run_id=_RUN_ID,
                reason="x",
            ),
            principal_id=_PRINCIPAL,
            correlation_id=_CORRELATION,
        )
