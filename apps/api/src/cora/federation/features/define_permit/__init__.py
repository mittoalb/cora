"""Vertical slice for the `DefinePermit` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.federation.features import define_permit

    cmd = define_permit.DefinePermit(
        peer_facility_code="aps-2bm",
        direction=Direction.OUTBOUND,
        allowed_credential_ids=frozenset({...}),
        allowed_payload_types=frozenset({"dataset/v1"}),
        allowed_artifact_kinds=frozenset({"tomogram"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=...,
        terms=OutboundTerms(...),
    )
    handler = define_permit.bind(deps)
    permit_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.federation.features.define_permit import tool
from cora.federation.features.define_permit.command import DefinePermit
from cora.federation.features.define_permit.decider import decide
from cora.federation.features.define_permit.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.federation.features.define_permit.route import router

__all__ = [
    "DefinePermit",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
