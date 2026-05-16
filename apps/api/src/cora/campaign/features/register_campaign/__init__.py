"""Vertical slice for the `RegisterCampaign` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.campaign.features import register_campaign

    cmd = register_campaign.RegisterCampaign(
        name="In-situ heating series #42",
        intent=CampaignIntent.SERIES,
        lead_actor_id=UUID("..."),
        ...,
    )
    handler = register_campaign.bind(deps)
    campaign_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.campaign.features.register_campaign import tool
from cora.campaign.features.register_campaign.command import RegisterCampaign
from cora.campaign.features.register_campaign.decider import decide
from cora.campaign.features.register_campaign.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.campaign.features.register_campaign.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "RegisterCampaign",
    "bind",
    "decide",
    "router",
    "tool",
]
