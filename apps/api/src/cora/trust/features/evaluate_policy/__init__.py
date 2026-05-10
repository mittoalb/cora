"""Vertical slice for the `EvaluatePolicy` query.

First Trust query slice. Module-as-namespace surface, symmetric
with `get_actor`:

    from cora.trust.features import evaluate_policy

    q = evaluate_policy.EvaluatePolicy(
        policy_id=...,
        subject_principal_id=...,
        subject_command_name="RegisterActor",
        subject_conduit_id=...,
    )
    handler = evaluate_policy.bind(deps)
    result = await handler(q, principal_id=..., correlation_id=...)
    # result is None | Allow() | Deny(reason=...)
"""

from cora.trust.features.evaluate_policy import tool
from cora.trust.features.evaluate_policy.handler import Handler, bind
from cora.trust.features.evaluate_policy.query import EvaluatePolicy
from cora.trust.features.evaluate_policy.route import router

__all__ = [
    "EvaluatePolicy",
    "Handler",
    "bind",
    "router",
    "tool",
]
