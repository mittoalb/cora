"""Evolver: replay events to reconstruct Campaign state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `CampaignEvent` without a matching match arm here.

Status mapping per event type (6 arms; 6i-a):

  - `CampaignRegistered` -> PLANNED   (genesis; status implicit)
  - `CampaignStarted`    -> ACTIVE    (single-source: Planned only)
  - `CampaignHeld`       -> HELD      (single-source: Active only;
                              sets `last_status_reason`)
  - `CampaignResumed`    -> ACTIVE    (single-source: Held only;
                              preserves `last_status_reason` --
                              audit breadcrumb "why was it held
                              before the resume?" stays readable)
  - `CampaignClosed`     -> CLOSED    (multi-source: Active | Held)
  - `CampaignAbandoned`  -> ABANDONED (multi-source: Planned | Active |
                              Held; sets `last_status_reason`)

Source-state guards live at the decider, NOT here; the evolver trusts
the event log (folded events have already passed their decider).

Transition events applied to empty state raise `ValueError` via the
shared `require_state` helper at `cora.infrastructure.evolver`.

`run_ids` stays empty across all 6 arms in 6i-a (no membership events
yet). In 6i-c the new `CampaignRunAdded` / `CampaignRunRemoved` arms
will mutate it; existing arms thread the field through unchanged.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.campaign.aggregates.campaign.events import (
    CampaignAbandoned,
    CampaignClosed,
    CampaignEvent,
    CampaignHeld,
    CampaignRegistered,
    CampaignResumed,
    CampaignStarted,
)
from cora.campaign.aggregates.campaign.state import (
    Campaign,
    CampaignDescription,
    CampaignIntent,
    CampaignName,
    CampaignStatus,
    CampaignTag,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Campaign | None, event: CampaignEvent) -> Campaign:
    """Apply one event to the current state."""
    match event:
        case CampaignRegistered(
            campaign_id=campaign_id,
            name=name,
            intent=intent,
            lead_actor_id=lead_actor_id,
            subject_id=subject_id,
            description=description,
            tags=tags,
            external_refs=external_refs,
            external_id=external_id,
        ):
            _ = state  # CampaignRegistered is the genesis event; prior state ignored
            return Campaign(
                id=campaign_id,
                name=CampaignName(name),
                intent=CampaignIntent(intent),
                lead_actor_id=lead_actor_id,
                subject_id=subject_id,
                description=(CampaignDescription(description) if description is not None else None),
                tags=frozenset(CampaignTag(t) for t in tags),
                external_refs=external_refs,
                external_id=external_id,
                status=CampaignStatus.PLANNED,
            )
        case CampaignStarted():
            prior = require_state(state, "CampaignStarted")
            return Campaign(
                id=prior.id,
                name=prior.name,
                intent=prior.intent,
                lead_actor_id=prior.lead_actor_id,
                subject_id=prior.subject_id,
                description=prior.description,
                tags=prior.tags,
                external_refs=prior.external_refs,
                external_id=prior.external_id,
                run_ids=prior.run_ids,
                status=CampaignStatus.ACTIVE,
                last_status_reason=prior.last_status_reason,
            )
        case CampaignHeld(reason=reason):
            prior = require_state(state, "CampaignHeld")
            return Campaign(
                id=prior.id,
                name=prior.name,
                intent=prior.intent,
                lead_actor_id=prior.lead_actor_id,
                subject_id=prior.subject_id,
                description=prior.description,
                tags=prior.tags,
                external_refs=prior.external_refs,
                external_id=prior.external_id,
                run_ids=prior.run_ids,
                status=CampaignStatus.HELD,
                last_status_reason=reason,
            )
        case CampaignResumed():
            prior = require_state(state, "CampaignResumed")
            return Campaign(
                id=prior.id,
                name=prior.name,
                intent=prior.intent,
                lead_actor_id=prior.lead_actor_id,
                subject_id=prior.subject_id,
                description=prior.description,
                tags=prior.tags,
                external_refs=prior.external_refs,
                external_id=prior.external_id,
                run_ids=prior.run_ids,
                status=CampaignStatus.ACTIVE,
                last_status_reason=prior.last_status_reason,
            )
        case CampaignClosed():
            prior = require_state(state, "CampaignClosed")
            return Campaign(
                id=prior.id,
                name=prior.name,
                intent=prior.intent,
                lead_actor_id=prior.lead_actor_id,
                subject_id=prior.subject_id,
                description=prior.description,
                tags=prior.tags,
                external_refs=prior.external_refs,
                external_id=prior.external_id,
                run_ids=prior.run_ids,
                status=CampaignStatus.CLOSED,
                last_status_reason=prior.last_status_reason,
            )
        case CampaignAbandoned(reason=reason):
            prior = require_state(state, "CampaignAbandoned")
            return Campaign(
                id=prior.id,
                name=prior.name,
                intent=prior.intent,
                lead_actor_id=prior.lead_actor_id,
                subject_id=prior.subject_id,
                description=prior.description,
                tags=prior.tags,
                external_refs=prior.external_refs,
                external_id=prior.external_id,
                run_ids=prior.run_ids,
                status=CampaignStatus.ABANDONED,
                last_status_reason=reason,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[CampaignEvent]) -> Campaign | None:
    """Replay a stream of events from the empty initial state."""
    state: Campaign | None = None
    for event in events:
        state = evolve(state, event)
    return state
