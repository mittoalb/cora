"""Shared beamtime-intake helper for operations-phase scenario tests.

Extracted when the 3rd operations-phase scenario re-did the intake
registration ceremony by hand (rule-of-three trigger fires,
matching the `_facility_fixture.py` extraction pattern).

The beamtime-intake source-of-truth scenario (`test_2bm_beamtime_intake`)
does NOT use this fixture: it IS the canonical intake
ceremony being tested. All subsequent operations-phase scenarios
(`mount_sample`, `tomography_scan`, `run_debrief`, `dismount_sample`,
`data_publish`) consume it.

## Two coupled helpers

`open_beamtime()` executes the intake ceremony (register PI Actor +
Subject + Campaign); `beamtime_id_prefix()` returns the matching
`FixedIdGenerator` queue prefix. Callers must use both together:
the prefix MUST sit AFTER `facility_id_prefix(...)` and BEFORE any
scenario-specific commands consume the queue. Drift corrupts every
downstream id allocation.

## Why scenario-supplied UUIDs (not canonical)

Same convention as `_facility_fixture.py`: each scenario tags its
aggregate ids with a mnemonic hex segment for audit-trail
traceability. The fixture must NOT pick canonical UUIDs; it accepts
whatever the caller declares as constants.

## Usage shape

```python
_BEAMTIME = BeamtimeSpec(
    pi_actor_id=_PI_ACTOR_ID,
    pi_actor_name="Proposal 2026-1234 PI",
    subject_id=_SUBJECT_ID,
    subject_name="porous sandstone core (Proposal 2026-1234, sample A)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="Proposal 2026-1234 beamtime",
    campaign_intent=CampaignIntent.COORDINATED,
    campaign_tags=frozenset({"proposal", "tomography", "porous_media"}),
)

def _id_queue() -> list[UUID]:
    return [
        *facility_id_prefix(...),
        # ... any per-device activate event ids
        *beamtime_id_prefix(spec=_BEAMTIME),
        # ... scenario-specific ids follow
    ]

async def test_...(db_pool):
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())
    await install_aps_unit(deps, devices=_DEVICES, ...)
    # ... activate devices
    await open_beamtime(
        deps,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        spec=_BEAMTIME,
    )
    # ... scenario-specific commands follow
```
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from cora.access.features.register_actor import RegisterActor
from cora.access.features.register_actor import bind as bind_register_actor
from cora.campaign.aggregates.campaign import CampaignIntent
from cora.campaign.features.register_campaign import RegisterCampaign
from cora.campaign.features.register_campaign import bind as bind_register_campaign
from cora.infrastructure.kernel import Kernel
from cora.subject.features.register_subject import RegisterSubject
from cora.subject.features.register_subject import bind as bind_register_subject


@dataclass(frozen=True)
class BeamtimeSpec:
    """Caller-supplied identity + display fields for the intake registrations.

    Mirrors the shape of `DeviceSpec` in `_facility_fixture.py`:
    caller pre-allocates the aggregate ids + supplies display names
    + chooses Campaign shape (intent, tags). Description is optional;
    omit by passing None (defaulted).
    """

    pi_actor_id: UUID
    pi_actor_name: str
    subject_id: UUID
    subject_name: str
    campaign_id: UUID
    campaign_name: str
    campaign_intent: CampaignIntent
    campaign_tags: frozenset[str] = frozenset()
    campaign_description: str | None = None


@dataclass(frozen=True)
class BeamtimeIds:
    """IDs of every aggregate registered by `open_beamtime()`."""

    pi_actor_id: UUID
    subject_id: UUID
    campaign_id: UUID


def beamtime_id_prefix(*, spec: BeamtimeSpec) -> list[UUID]:
    """FixedIdGenerator queue prefix for `open_beamtime()`.

    Three register pairs, in order:
      1. register_actor (PI): pi_actor_id, event
      2. register_subject (sample): subject_id, event
      3. register_campaign (proposal-scoped): campaign_id, event

    Anonymous event ids use `uuid4()`. Total length = 6.
    """
    e = uuid4
    return [
        spec.pi_actor_id,
        e(),
        spec.subject_id,
        e(),
        spec.campaign_id,
        e(),
    ]


async def open_beamtime(
    deps: Kernel,
    *,
    principal_id: UUID,
    correlation_id: UUID,
    spec: BeamtimeSpec,
) -> BeamtimeIds:
    """Execute the canonical intake ceremony.

    Operator (principal) registers the PI Actor (acting on PI's
    behalf, LIMS Study Director precedent), registers the incoming
    Subject (lands in Received), opens the proposal-scoped Campaign
    with PI as `lead_actor_id` and Subject as `subject_id`.

    Order matches `beamtime_id_prefix()` exactly.
    """
    await bind_register_actor(deps)(
        RegisterActor(name=spec.pi_actor_name),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    await bind_register_subject(deps)(
        RegisterSubject(name=spec.subject_name),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    await bind_register_campaign(deps)(
        RegisterCampaign(
            name=spec.campaign_name,
            intent=spec.campaign_intent,
            lead_actor_id=spec.pi_actor_id,
            subject_id=spec.subject_id,
            description=spec.campaign_description,
            tags=spec.campaign_tags,
        ),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    return BeamtimeIds(
        pi_actor_id=spec.pi_actor_id,
        subject_id=spec.subject_id,
        campaign_id=spec.campaign_id,
    )


__all__ = [
    "BeamtimeIds",
    "BeamtimeSpec",
    "beamtime_id_prefix",
    "open_beamtime",
]
