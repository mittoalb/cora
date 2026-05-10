"""TrustAuthorize: production adapter for the cross-BC `Authorize` port.

Implements `cora.infrastructure.ports.Authorize` by loading a single
configured Policy aggregate and delegating to the pure
`evaluate(policy, ...)` function from `aggregates/policy/state.py`.
This is the structural moment where Phase 3's pure domain logic
(Zone / Conduit / Policy + define + evaluate) gates real commands
across every BC.

## Phase 3e shape: single configured policy

The constructor takes one `policy_id`. Every `__call__(...)` loads
that policy via `load_policy` (fold-on-read; O(events-per-stream)
per request) and evaluates against it.

This deliberately ships the smallest useful gating wire-up:
- One policy per deployment (set via `Settings.trust_authz_policy_id`)
- No projection / cross-stream resolution
- No caching (each request hits the event store)

Multi-policy resolution + caching + LISTEN/NOTIFY invalidation land
in later phases when projection-worker infrastructure exists.

## Conduit semantics (post-3h)

The port passes `conduit_id: UUID` (was `conduit: str` in Phase 3e —
3g typed the parameter, 3h activates it). TrustAuthorize forwards
the caller's `conduit_id` to `evaluate`, which means a policy bound
to one conduit naturally denies calls on another via evaluate's
existing conduit-mismatch check.

Operational consequence: deployments wire `Settings.trust_authz_policy_id`
to a Policy whose `conduit_id` matches what handlers pass. Today
every handler passes `UUID(int=0)` (nil sentinel; surface-level
conduit injection is the next step), so the gating policy must use
`conduit_id=UUID(int=0)`. Once HTTP / MCP / A2A surfaces start
injecting their own conduit_ids, deployments will define one Policy
per conduit (single-policy-per-deployment shape stays; the operator
picks which conduit to gate first, others fall through to deny).

## Bootstrap problem

If the configured policy doesn't permit `DefinePolicy`, you can't
define new policies through the API. Deployment workflow:

    1. Start with `trust_authz_policy_id` unset (AllowAllAuthorize).
    2. `POST /policies` with a permissive policy; record the id.
    3. Restart with `trust_authz_policy_id` = that id.

A "system bootstrap policy" auto-defined via migration would close
this gap; deferred until modify_policy + status lifecycle land.

## Caller authz vs evaluation result

`Authorize.__call__` returns `Allow` or `Deny`. From the caller's
perspective there's no distinction between "the policy permits you"
(Allow) and "no policy applies / always Allow" (Allow); both gate
through. Same for Deny — the reason string carries the diagnostic
("Principal X not in policy Y's permitted set" vs "Configured
TrustAuthorize policy Y not found in event store").

If the configured policy is missing from the event store, this
adapter returns Deny — fail-closed. A Settings-time check that the
policy exists at startup would surface this earlier; deferred.
"""

from uuid import UUID

from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Allow, AuthzResult, Deny, EventStore
from cora.trust.aggregates.policy import evaluate, load_policy

_log = get_logger(__name__)


class TrustAuthorize:
    """Authorize port adapter that gates via a single configured Policy."""

    def __init__(self, event_store: EventStore, *, policy_id: UUID) -> None:
        self._event_store = event_store
        self._policy_id = policy_id

    async def __call__(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
    ) -> AuthzResult:
        policy = await load_policy(self._event_store, self._policy_id)
        if policy is None:
            _log.warning(
                "trust_authorize.policy_missing",
                policy_id=str(self._policy_id),
                principal_id=str(principal_id),
                command_name=command_name,
                conduit_id=str(conduit_id),
            )
            return Deny(
                reason=(
                    f"Configured TrustAuthorize policy {self._policy_id} not found in event store"
                )
            )

        # 3h: forward caller's conduit_id (was policy.conduit_id in
        # Phase 3e). evaluate's conduit-mismatch check now meaningfully
        # gates calls — a policy bound to one conduit denies calls on
        # another instead of being evaluated as if it were governing.
        result = evaluate(
            policy,
            principal_id=principal_id,
            command_name=command_name,
            conduit_id=conduit_id,
        )
        if isinstance(result, Allow):
            _log.info(
                "trust_authorize.allow",
                policy_id=str(self._policy_id),
                principal_id=str(principal_id),
                command_name=command_name,
            )
        else:
            _log.info(
                "trust_authorize.deny",
                policy_id=str(self._policy_id),
                principal_id=str(principal_id),
                command_name=command_name,
                reason=result.reason,
            )
        return result
