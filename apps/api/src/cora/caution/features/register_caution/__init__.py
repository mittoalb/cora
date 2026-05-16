"""Vertical slice for the `RegisterCaution` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.caution.features import register_caution

    cmd = register_caution.RegisterCaution(target=..., category=...,
                                           severity=..., text="...",
                                           workaround="...",
                                           author_actor_id=...)
    handler = register_caution.bind(deps)
    caution_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.caution.features.register_caution import tool
from cora.caution.features.register_caution.command import RegisterCaution
from cora.caution.features.register_caution.decider import decide
from cora.caution.features.register_caution.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.caution.features.register_caution.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "RegisterCaution",
    "bind",
    "decide",
    "router",
    "tool",
]
