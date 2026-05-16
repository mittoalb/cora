"""Vertical slice for the `CloseCampaign` command."""

from cora.campaign.features.close_campaign import tool
from cora.campaign.features.close_campaign.command import CloseCampaign
from cora.campaign.features.close_campaign.decider import decide
from cora.campaign.features.close_campaign.handler import Handler, bind
from cora.campaign.features.close_campaign.route import router

__all__ = [
    "CloseCampaign",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
