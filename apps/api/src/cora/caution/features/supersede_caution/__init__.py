"""Vertical slice for the `SupersedeCaution` command.

Cross-aggregate cousin of `register_caution`: takes an Active parent
caution and atomically writes (a) the parent's `CautionSuperseded`
event on the parent stream and (b) the child's `CautionRegistered`
genesis event on a new child stream. Both writes via
`EventStore.append_streams` (single Postgres transaction; all-or-
nothing). Mirrors Safety BC's `amend_clearance` slice shape.
"""

from cora.caution.features.supersede_caution import tool
from cora.caution.features.supersede_caution.command import SupersedeCaution
from cora.caution.features.supersede_caution.context import CautionSupersessionContext
from cora.caution.features.supersede_caution.decider import SupersessionEvents, decide
from cora.caution.features.supersede_caution.handler import Handler, IdempotentHandler, bind
from cora.caution.features.supersede_caution.route import router

__all__ = [
    "CautionSupersessionContext",
    "Handler",
    "IdempotentHandler",
    "SupersedeCaution",
    "SupersessionEvents",
    "bind",
    "decide",
    "router",
    "tool",
]
