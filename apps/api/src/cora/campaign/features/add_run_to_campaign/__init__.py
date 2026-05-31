"""Vertical slice for the `AddRunToCampaign` command.

Cross-aggregate membership-add slice: writes `CampaignRunAdded` to
the Campaign's stream AND `RunAddedToCampaign` to the Run's stream
atomically via `EventStore.append_streams` (mirrors Safety's
`amend_clearance` shape).
"""

from cora.campaign.features.add_run_to_campaign import tool
from cora.campaign.features.add_run_to_campaign.command import AddRunToCampaign
from cora.campaign.features.add_run_to_campaign.context import CampaignMembershipContext
from cora.campaign.features.add_run_to_campaign.decider import MembershipEvents, decide
from cora.campaign.features.add_run_to_campaign.handler import Handler, bind
from cora.campaign.features.add_run_to_campaign.route import router

__all__ = [
    "AddRunToCampaign",
    "CampaignMembershipContext",
    "Handler",
    "MembershipEvents",
    "bind",
    "decide",
    "router",
    "tool",
]
