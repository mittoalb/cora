"""Vertical slice for the `StartSealRepublishing` command.

Module-as-namespace surface, symmetric with the other Federation
transition slices:

    from cora.federation.features import start_seal_republishing

    cmd = start_seal_republishing.StartSealRepublishing(
        facility_id=...,
        reason=...,
    )
    handler = start_seal_republishing.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Single-source transition: requires the Seal to be in `Live` status.
Strict-not-idempotent: starting a republishing window against a Seal
already in `Republishing` raises `SealCannotStartRepublishingError`
(HTTP 409). The aggregate flips to `Republishing` and stays there
until `complete_seal_republishing` returns it to `Live`. The online
key continues to sign pointers during the window; consumers may use
the `Republishing` indicator to defer trust.
"""

from cora.federation.features.start_seal_republishing import tool
from cora.federation.features.start_seal_republishing.command import (
    StartSealRepublishing,
)
from cora.federation.features.start_seal_republishing.decider import decide
from cora.federation.features.start_seal_republishing.handler import Handler, bind
from cora.federation.features.start_seal_republishing.route import router

__all__ = [
    "Handler",
    "StartSealRepublishing",
    "bind",
    "decide",
    "router",
    "tool",
]
