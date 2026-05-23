"""Vertical slice for the `ForgetActor` command (PII erasure).

Module-as-namespace surface:

    from cora.access.features import forget_actor

    cmd = forget_actor.ForgetActor(actor_id=...)
    handler = forget_actor.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

The slice implements GDPR / PIPL / LGPD / CCPA "right to be
forgotten" for the `actor_profile` PII vault per
[[project_pii_vault_implementation_design]] §"Slice — forget_actor".
The handler scrubs + deletes the profile row AND appends an
`ActorProfileForgotten` audit event in ONE Postgres transaction,
so the event log carries a permanent who/when audit trail while
the PII column is overwritten before its dead-tuple bytes are
VACUUM'd.
"""

from cora.access.features.forget_actor import tool
from cora.access.features.forget_actor.command import ForgetActor
from cora.access.features.forget_actor.decider import decide
from cora.access.features.forget_actor.handler import Handler, IdempotentHandler, bind
from cora.access.features.forget_actor.route import router

__all__ = [
    "ForgetActor",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
