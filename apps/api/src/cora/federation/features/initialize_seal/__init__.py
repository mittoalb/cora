"""Vertical slice for the `InitializeSeal` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.federation.features import initialize_seal

    cmd = initialize_seal.InitializeSeal(
        facility_id="aps-2bm",
        online_key_ref=online_credential_id,
        offline_key_ref=offline_credential_id,
    )
    handler = initialize_seal.bind(deps)
    seal_stream_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.federation.features.initialize_seal import tool
from cora.federation.features.initialize_seal.command import InitializeSeal
from cora.federation.features.initialize_seal.decider import decide
from cora.federation.features.initialize_seal.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.federation.features.initialize_seal.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "InitializeSeal",
    "bind",
    "decide",
    "router",
    "tool",
]
