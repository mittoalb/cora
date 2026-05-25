"""Shared seed helpers for Campaign transition-handler tests.

Each helper appends events to a fresh `InMemoryEventStore` so a
transition handler can be exercised against a known starting state.
The Campaign update-handler factory (per-aggregate thin wrapper
over the cross-BC `make_update_handler`) is well-tested via its
own infrastructure tests + via Supply / Safety transition tests;
Campaign transition tests focus on factory wiring + envelope
plumbing, NOT on re-testing every code path of the factory.
"""

from datetime import UTC, datetime
from uuid import UUID

from cora.campaign.aggregates.campaign import (
    CampaignHeld,
    CampaignRegistered,
    CampaignStarted,
    event_type_name,
    to_payload,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event

PRIOR = datetime(2026, 5, 16, 11, 0, 0, tzinfo=UTC)
NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)

CAMPAIGN_ID = UUID("01900000-0000-7000-8000-0000000c5001")
LEAD_ACTOR_ID = UUID("01900000-0000-7000-8000-0000000c5099")
PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c5101")
STARTED_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c5102")
HELD_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c5103")
TRANSITION_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c5104")


async def _append(
    store: InMemoryEventStore,
    event: object,
    event_id: UUID,
    command_name: str,
) -> None:
    new_event = to_new_event(
        event_type=event_type_name(event),  # type: ignore[arg-type]
        payload=to_payload(event),  # type: ignore[arg-type]
        occurred_at=event.occurred_at,  # type: ignore[attr-defined]
        event_id=event_id,
        command_name=command_name,
        correlation_id=CORRELATION_ID,
        causation_id=None,
        principal_id=PRINCIPAL_ID,
    )
    version_before = (await store.load("Campaign", CAMPAIGN_ID))[1]
    await store.append(
        stream_type="Campaign",
        stream_id=CAMPAIGN_ID,
        expected_version=version_before,
        events=[new_event],
    )


async def seed_planned(store: InMemoryEventStore) -> None:
    """Seed a registered Campaign (status = Planned)."""
    await _append(
        store,
        CampaignRegistered(
            campaign_id=CAMPAIGN_ID,
            name="test",
            intent="Series",
            lead_actor_id=LEAD_ACTOR_ID,
            subject_id=None,
            description=None,
            tags=frozenset(),
            external_refs=frozenset(),
            external_id=None,
            occurred_at=PRIOR,
        ),
        GENESIS_EVENT_ID,
        "RegisterCampaign",
    )


async def seed_active(store: InMemoryEventStore) -> None:
    """Seed a registered + started Campaign (status = Active)."""
    await seed_planned(store)
    await _append(
        store,
        CampaignStarted(campaign_id=CAMPAIGN_ID, occurred_at=PRIOR),
        STARTED_EVENT_ID,
        "StartCampaign",
    )


async def seed_held(store: InMemoryEventStore) -> None:
    """Seed a registered + started + held Campaign (status = Held)."""
    await seed_active(store)
    await _append(
        store,
        CampaignHeld(campaign_id=CAMPAIGN_ID, reason="seed reason", occurred_at=PRIOR),
        HELD_EVENT_ID,
        "HoldCampaign",
    )
