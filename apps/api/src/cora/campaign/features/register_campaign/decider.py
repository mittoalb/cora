"""Pure decider for the `RegisterCampaign` command.

Pure function: given the current Campaign state (None for a fresh
stream) and a `RegisterCampaign` command, returns the events to
append. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports (the non-determinism principle:
capture, don't recompute).

## Validation (in order)

  - State must be None (genesis-only) -> `CampaignAlreadyExistsError`
  - `name` wrapped via `CampaignName(...)`; 1-200 chars after trim ->
    `InvalidCampaignNameError`
  - `description`, if provided, wrapped via `CampaignDescription(...)`;
    1-2000 chars after trim -> `InvalidCampaignDescriptionError`
  - Each `tag` wrapped via `CampaignTag(...)`; 1-50 chars after trim
    -> `InvalidCampaignTagError`. Empty tags-set IS allowed (the
    closed `intent` enum carries the discriminator weight).
  - `external_refs` validated by the `ExternalRef` VO at command-build
    time; this decider trusts the typed input. (Re-validation here
    would duplicate the `__post_init__` bound check; if a future
    serialization path bypasses the VO, add a defensive
    re-construction here.)
  - `external_id`, if provided: 1-100 chars after trim ->
    `InvalidCampaignExternalIdError`. Bare-str validated.

`lead_actor_id` is a passthrough from the command (operator-asserted
campaign lead; may differ from envelope principal_id per design
memo lock + LIMS Study Director precedent).

Initial status is implicit `Planned` (event type IS the state-change
indicator; the genesis evolver hardcodes the mapping). The single
emitted event is `CampaignRegistered`.
"""

from datetime import datetime
from uuid import UUID

from cora.campaign.aggregates.campaign import (
    CAMPAIGN_EXTERNAL_ID_MAX_LENGTH,
    Campaign,
    CampaignAlreadyExistsError,
    CampaignDescription,
    CampaignName,
    CampaignRegistered,
    CampaignTag,
    InvalidCampaignExternalIdError,
)
from cora.campaign.features.register_campaign.command import RegisterCampaign


def decide(
    state: Campaign | None,
    command: RegisterCampaign,
    *,
    now: datetime,
    new_id: UUID,
) -> list[CampaignRegistered]:
    """Decide the events produced by registering a new Campaign."""
    if state is not None:
        raise CampaignAlreadyExistsError(state.id)

    # Validate + trim text fields via VOs.
    name = CampaignName(command.name)
    description: CampaignDescription | None = (
        CampaignDescription(command.description) if command.description is not None else None
    )
    tags = frozenset(CampaignTag(t) for t in command.tags)

    # Bare-str external_id validation (no VO; lazy-mint field).
    external_id: str | None = None
    if command.external_id is not None:
        trimmed = command.external_id.strip()
        if not trimmed or len(trimmed) > CAMPAIGN_EXTERNAL_ID_MAX_LENGTH:
            raise InvalidCampaignExternalIdError(command.external_id)
        external_id = trimmed

    return [
        CampaignRegistered(
            campaign_id=new_id,
            name=name.value,
            intent=command.intent.value,
            lead_actor_id=command.lead_actor_id,
            subject_id=command.subject_id,
            description=description.value if description is not None else None,
            tags=frozenset(t.value for t in tags),
            external_refs=command.external_refs,
            external_id=external_id,
            occurred_at=now,
        )
    ]
