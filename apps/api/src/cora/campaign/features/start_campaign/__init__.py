"""Vertical slice for the `StartCampaign` command."""

from cora.campaign.features.start_campaign import tool
from cora.campaign.features.start_campaign.command import StartCampaign
from cora.campaign.features.start_campaign.decider import decide
from cora.campaign.features.start_campaign.handler import Handler, bind
from cora.campaign.features.start_campaign.route import router

__all__ = [
    "Handler",
    "StartCampaign",
    "bind",
    "decide",
    "router",
    "tool",
]
