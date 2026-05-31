"""Vertical slice for the `RemoveRunFromCampaign` command.

Cross-aggregate membership-remove slice: writes `CampaignRunRemoved`
to the Campaign's stream AND `RunRemovedFromCampaign` to the Run's
stream atomically via `EventStore.append_streams` (mirrors Safety's
`amend_clearance` shape).
"""

from cora.campaign.features.remove_run_from_campaign import tool
from cora.campaign.features.remove_run_from_campaign.command import RemoveRunFromCampaign
from cora.campaign.features.remove_run_from_campaign.context import CampaignMembershipContext
from cora.campaign.features.remove_run_from_campaign.decider import MembershipEvents, decide
from cora.campaign.features.remove_run_from_campaign.handler import Handler, bind
from cora.campaign.features.remove_run_from_campaign.route import router

__all__ = [
    "CampaignMembershipContext",
    "Handler",
    "MembershipEvents",
    "RemoveRunFromCampaign",
    "bind",
    "decide",
    "router",
    "tool",
]
