"""Vertical slice for the `CompleteSealRepublishing` command.

Module-as-namespace surface, symmetric with the other Federation
transition slices:

    from cora.federation.features import complete_seal_republishing

    cmd = complete_seal_republishing.CompleteSealRepublishing(
        facility_id=...,
        new_head_hash=...,
        new_sequence_number=...,
    )
    handler = complete_seal_republishing.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Single-source transition (Republishing -> Live): the back-edge closes
the republish window, optionally publishing a fresh head pointer when
`new_head_hash` and `new_sequence_number` are supplied together.
Strict-not-idempotent at the decider: completing on a non-Republishing
Seal raises `SealCannotCompleteRepublishingError` (HTTP 409).
"""

from cora.federation.features.complete_seal_republishing import tool
from cora.federation.features.complete_seal_republishing.command import (
    CompleteSealRepublishing,
)
from cora.federation.features.complete_seal_republishing.decider import decide
from cora.federation.features.complete_seal_republishing.handler import Handler, bind
from cora.federation.features.complete_seal_republishing.route import router

__all__ = [
    "CompleteSealRepublishing",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
