"""Vertical slice for the `RegisterPermit` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.federation.features import register_permit

    cmd = register_permit.RegisterPermit(
        peer_facility_id="aps-2bm",
        direction=Direction.OUTBOUND,
        allowed_credentials=frozenset({...}),
        allowed_payload_types=frozenset({"dataset/v1"}),
        permitted_artifact_kinds=frozenset({"tomogram"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=...,
        terms=OutboundTerms(...),
    )
    handler = register_permit.bind(deps)
    permit_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.federation.features.register_permit import tool
from cora.federation.features.register_permit.command import RegisterPermit
from cora.federation.features.register_permit.decider import decide
from cora.federation.features.register_permit.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.federation.features.register_permit.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "RegisterPermit",
    "bind",
    "decide",
    "router",
    "tool",
]
