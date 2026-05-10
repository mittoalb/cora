"""Vertical slice for the `DefinePolicy` command.

Module-as-namespace surface:

    from cora.trust.features import define_policy

    cmd = define_policy.DefinePolicy(
        name="Beam-team-PSS",
        conduit_id=...,
        permitted_principals=frozenset({...}),
        permitted_commands=frozenset({"RegisterActor"}),
    )
    handler = define_policy.bind(deps)
    policy_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.trust.features.define_policy import tool
from cora.trust.features.define_policy.command import DefinePolicy
from cora.trust.features.define_policy.decider import decide
from cora.trust.features.define_policy.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.trust.features.define_policy.route import router

__all__ = [
    "DefinePolicy",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
