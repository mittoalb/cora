"""Vertical slice for the `GetCampaign` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.campaign.features import get_campaign

    q = get_campaign.GetCampaign(campaign_id=...)
    handler = get_campaign.bind(deps)
    campaign = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.campaign.features.get_campaign import tool
from cora.campaign.features.get_campaign.handler import Handler, bind
from cora.campaign.features.get_campaign.query import GetCampaign
from cora.campaign.features.get_campaign.route import router

__all__ = [
    "GetCampaign",
    "Handler",
    "bind",
    "router",
    "tool",
]
