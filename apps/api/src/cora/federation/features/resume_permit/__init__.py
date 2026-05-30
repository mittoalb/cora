"""Vertical slice for the `ResumePermit` command.

Module-as-namespace surface, symmetric with the other Federation
transition slices:

    from cora.federation.features import resume_permit

    cmd = resume_permit.ResumePermit(permit_id=...)
    handler = resume_permit.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Audit twin of `activate_permit`: same target status (Active) but
distinct event type (`PermitResumed`) so projections and audit
queries can separate the first-activation gesture from the
resume-after-suspend gesture.
"""

from cora.federation.features.resume_permit import tool
from cora.federation.features.resume_permit.command import ResumePermit
from cora.federation.features.resume_permit.decider import decide
from cora.federation.features.resume_permit.handler import Handler, bind
from cora.federation.features.resume_permit.route import router

__all__ = [
    "Handler",
    "ResumePermit",
    "bind",
    "decide",
    "router",
    "tool",
]
