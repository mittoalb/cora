"""Application-handler tests for `get_campaign` query slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.campaign.aggregates.campaign import (
    CampaignIntent,
    CampaignStatus,
    event_type_name,
    to_payload,
)
from cora.campaign.aggregates.campaign.events import CampaignRegistered
from cora.campaign.errors import UnauthorizedError
from cora.campaign.features import get_campaign
from cora.campaign.features.get_campaign import GetCampaign
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.memory.event_store import InMemoryEventStore
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000060001")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000060002")
_LEAD_ACTOR_ID = UUID("01900000-0000-7000-8000-000000060003")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed(store: InMemoryEventStore) -> None:
    genesis = CampaignRegistered(
        campaign_id=_CAMPAIGN_ID,
        name="In-situ heating",
        intent="Series",
        lead_actor_id=_LEAD_ACTOR_ID,
        subject_id=None,
        description=None,
        tags=frozenset(),
        external_refs=frozenset(),
        external_id=None,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(genesis),
        payload=to_payload(genesis),
        occurred_at=genesis.occurred_at,
        event_id=_GENESIS_EVENT_ID,
        command_name="RegisterCampaign",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_LEAD_ACTOR_ID,
    )
    await store.append(
        stream_type="Campaign",
        stream_id=_CAMPAIGN_ID,
        expected_version=0,
        events=[new_event],
    )


@pytest.mark.unit
async def test_handler_returns_campaign_on_hit() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler = get_campaign.bind(deps)
    campaign = await handler(
        GetCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert campaign is not None
    assert campaign.id == _CAMPAIGN_ID
    assert campaign.status == CampaignStatus.PLANNED
    assert campaign.intent == CampaignIntent.SERIES
    assert campaign.lead_actor_id == _LEAD_ACTOR_ID
    assert campaign.name.value == "In-situ heating"


@pytest.mark.unit
async def test_handler_returns_none_on_miss() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler = get_campaign.bind(deps)
    campaign = await handler(
        GetCampaign(campaign_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert campaign is None


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store, deny=True)
    handler = get_campaign.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            GetCampaign(campaign_id=_CAMPAIGN_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
