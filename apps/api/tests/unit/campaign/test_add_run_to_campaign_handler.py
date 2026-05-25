"""Application-handler tests for `add_run_to_campaign` slice.

Pre-load both streams, decide, write both atomically via
EventStore.append_streams.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.campaign.aggregates.campaign import (
    CampaignNotFoundError,
    CampaignRegistered,
    CampaignRunAlreadyMemberError,
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
from cora.campaign.errors import UnauthorizedError
from cora.campaign.features import add_run_to_campaign
from cora.campaign.features.add_run_to_campaign import AddRunToCampaign
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
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

_NOW = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 5, 17, 13, 0, 0, tzinfo=UTC)
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000ee0001")
_RUN_ID = UUID("01900000-0000-7000-8000-000000ee0002")
_LEAD = UUID("01900000-0000-7000-8000-000000ee00aa")
_PLAN = UUID("01900000-0000-7000-8000-000000ee00bb")
_PRINCIPAL = UUID("01900000-0000-7000-8000-000000ee0099")
_CORRELATION = UUID("01900000-0000-7000-8000-000000ee00cc")


async def _seed_campaign(store: InMemoryEventStore) -> None:
    """Seed a Campaign in Active status."""
    for idx, event in enumerate(
        [
            CampaignRegistered(
                campaign_id=_CAMPAIGN_ID,
                name="campaign",
                intent="Series",
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
    """Seed a standalone Run (no campaign_id)."""
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


@pytest.mark.unit
async def test_handler_writes_both_streams_atomically() -> None:
    store = InMemoryEventStore()
    await _seed_campaign(store)
    await _seed_run(store)

    deps = build_deps(
        now=_NOW,
        event_store=store,
        ids=[uuid4(), uuid4()],
    )
    handler = add_run_to_campaign.bind(deps)
    await handler(
        AddRunToCampaign(campaign_id=_CAMPAIGN_ID, run_id=_RUN_ID),
        principal_id=_PRINCIPAL,
        correlation_id=_CORRELATION,
    )

    campaign_stored, _ = await store.load("Campaign", _CAMPAIGN_ID)
    campaign_state = campaign_fold([campaign_from_stored(s) for s in campaign_stored])
    assert campaign_state is not None
    assert _RUN_ID in campaign_state.run_ids

    run_stored, _ = await store.load("Run", _RUN_ID)
    run_state = run_fold([run_from_stored(s) for s in run_stored])
    assert run_state is not None
    assert run_state.campaign_id == _CAMPAIGN_ID


@pytest.mark.unit
async def test_handler_raises_campaign_not_found_when_missing() -> None:
    store = InMemoryEventStore()
    await _seed_run(store)
    deps = build_deps(now=_NOW, event_store=store, ids=[uuid4(), uuid4()])
    handler = add_run_to_campaign.bind(deps)
    with pytest.raises(CampaignNotFoundError):
        await handler(
            AddRunToCampaign(campaign_id=_CAMPAIGN_ID, run_id=_RUN_ID),
            principal_id=_PRINCIPAL,
            correlation_id=_CORRELATION,
        )


@pytest.mark.unit
async def test_handler_raises_run_not_found_when_missing() -> None:
    store = InMemoryEventStore()
    await _seed_campaign(store)
    deps = build_deps(now=_NOW, event_store=store, ids=[uuid4(), uuid4()])
    handler = add_run_to_campaign.bind(deps)
    with pytest.raises(RunNotFoundError):
        await handler(
            AddRunToCampaign(campaign_id=_CAMPAIGN_ID, run_id=_RUN_ID),
            principal_id=_PRINCIPAL,
            correlation_id=_CORRELATION,
        )


@pytest.mark.unit
async def test_handler_raises_already_member_when_re_add() -> None:
    """Second add of the same Run -> CampaignRunAlreadyMemberError."""
    store = InMemoryEventStore()
    await _seed_campaign(store)
    await _seed_run(store)
    deps = build_deps(
        now=_NOW,
        event_store=store,
        ids=[uuid4() for _ in range(8)],
    )
    handler = add_run_to_campaign.bind(deps)
    await handler(
        AddRunToCampaign(campaign_id=_CAMPAIGN_ID, run_id=_RUN_ID),
        principal_id=_PRINCIPAL,
        correlation_id=_CORRELATION,
    )
    with pytest.raises(CampaignRunAlreadyMemberError):
        await handler(
            AddRunToCampaign(campaign_id=_CAMPAIGN_ID, run_id=_RUN_ID),
            principal_id=_PRINCIPAL,
            correlation_id=_CORRELATION,
        )


@pytest.mark.unit
async def test_handler_denies_on_authz_deny() -> None:
    store = InMemoryEventStore()
    await _seed_campaign(store)
    await _seed_run(store)
    deps = build_deps(
        now=_NOW,
        event_store=store,
        ids=[uuid4(), uuid4()],
        deny=True,
    )
    handler = add_run_to_campaign.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            AddRunToCampaign(campaign_id=_CAMPAIGN_ID, run_id=_RUN_ID),
            principal_id=_PRINCIPAL,
            correlation_id=_CORRELATION,
        )
