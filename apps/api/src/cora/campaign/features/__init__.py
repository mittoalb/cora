"""Vertical slices owned by the Campaign BC.

Each subdirectory is one slice with the standard six-file shape:
__init__, command (or query), decider (commands only), handler,
route, tool. See `cora.campaign` package docstring for the
module-as-namespace surface.

Phase 6i-a ships the 7 lifecycle slices (register, get, start, hold,
resume, close, abandon). Phase 6i-b adds `list_campaigns` (projection-
backed list). Phase 6i-c adds the cross-aggregate membership slices.
"""

from cora.campaign.features import (
    abandon_campaign,
    add_run_to_campaign,
    close_campaign,
    get_campaign,
    hold_campaign,
    list_campaigns,
    register_campaign,
    remove_run_from_campaign,
    resume_campaign,
    start_campaign,
)

__all__ = [
    "abandon_campaign",
    "add_run_to_campaign",
    "close_campaign",
    "get_campaign",
    "hold_campaign",
    "list_campaigns",
    "register_campaign",
    "remove_run_from_campaign",
    "resume_campaign",
    "start_campaign",
]
