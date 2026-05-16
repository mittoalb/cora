"""Compose the Campaign BC's handlers from `Kernel`.

`wire_campaign(deps)` is invoked once from the FastAPI lifespan and
the returned `CampaignHandlers` bundle is stored on
`app.state.campaign`. Routes and MCP tools pull their handler out of
that bundle. New slices add a new field on `CampaignHandlers` and a
single line in this factory.

Cross-cutting decorators applied here mirror Access / Trust /
Subject / Equipment / Supply / Safety / Caution:

  1. `bind(deps)` -- bare handler.
  2. `with_idempotency` (create-style commands only) -- Idempotency-
     Key support. Wrapped before tracing so cache-hits and cache-
     misses both attribute to the tracing span.
  3. `with_tracing` -- OTel span around every handler call.

## Wired handlers (6i-a)

  - `register_campaign` (create-style; idempotency-wrapped)
  - `start_campaign`    (transition; no idempotency wrap)
  - `hold_campaign`     (transition; no idempotency wrap)
  - `resume_campaign`   (transition; no idempotency wrap)
  - `close_campaign`    (transition; no idempotency wrap)
  - `abandon_campaign`  (transition; no idempotency wrap)
  - `get_campaign`      (query)
"""

from dataclasses import dataclass
from uuid import UUID

from cora.campaign.features import (
    abandon_campaign,
    close_campaign,
    get_campaign,
    hold_campaign,
    register_campaign,
    resume_campaign,
    start_campaign,
)
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing

_BC = "campaign"


@dataclass(frozen=True)
class CampaignHandlers:
    """The Campaign BC's handler bundle, each closed over Kernel."""

    register_campaign: register_campaign.IdempotentHandler
    start_campaign: start_campaign.Handler
    hold_campaign: hold_campaign.Handler
    resume_campaign: resume_campaign.Handler
    close_campaign: close_campaign.Handler
    abandon_campaign: abandon_campaign.Handler
    get_campaign: get_campaign.Handler


def wire_campaign(deps: Kernel) -> CampaignHandlers:
    """Build the Campaign BC handlers from shared dependencies."""
    return CampaignHandlers(
        register_campaign=with_tracing(
            with_idempotency(
                register_campaign.bind(deps),
                deps.idempotency_store,
                command_name="RegisterCampaign",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterCampaign",
            bc=_BC,
        ),
        start_campaign=with_tracing(
            start_campaign.bind(deps),
            command_name="StartCampaign",
            bc=_BC,
        ),
        hold_campaign=with_tracing(
            hold_campaign.bind(deps),
            command_name="HoldCampaign",
            bc=_BC,
        ),
        resume_campaign=with_tracing(
            resume_campaign.bind(deps),
            command_name="ResumeCampaign",
            bc=_BC,
        ),
        close_campaign=with_tracing(
            close_campaign.bind(deps),
            command_name="CloseCampaign",
            bc=_BC,
        ),
        abandon_campaign=with_tracing(
            abandon_campaign.bind(deps),
            command_name="AbandonCampaign",
            bc=_BC,
        ),
        get_campaign=with_tracing(
            get_campaign.bind(deps),
            command_name="GetCampaign",
            bc=_BC,
            kind="query",
        ),
    )
