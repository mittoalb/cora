"""Vertical slice for the `AmendClearance` command.

Cross-aggregate cousin of `register_clearance`: takes an Active parent
clearance and atomically writes (a) the parent's `ClearanceSuperseded`
event on the parent stream and (b) the child's `ClearanceRegistered`
genesis event on a new child stream. Both writes via
`EventStore.append_streams` (single Postgres transaction; all-or-
nothing).

The two-stream atomic write is CORA's first use of the multi-stream
EventStore capability. See the design memo's
"amend_clearance" section + the `EventStore.append_streams` port
docstring for the rationale.
"""

from cora.safety.features.amend_clearance import tool
from cora.safety.features.amend_clearance.command import AmendClearance
from cora.safety.features.amend_clearance.context import ClearanceAmendmentContext
from cora.safety.features.amend_clearance.decider import AmendmentEvents, decide
from cora.safety.features.amend_clearance.handler import Handler, IdempotentHandler, bind
from cora.safety.features.amend_clearance.route import router

__all__ = [
    "AmendClearance",
    "AmendmentEvents",
    "ClearanceAmendmentContext",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
