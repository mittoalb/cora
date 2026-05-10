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

## Conduit semantics (post-3g)

The port shape now passes `conduit_id: UUID` (was `conduit: str` in
Phase 3e — a sentinel "default" that this adapter ignored). 3g
typed the parameter; 3g still ignores it at evaluation time — the
configured policy's `conduit_id` is what evaluate checks against.
3h will flip this so evaluate receives the caller's `conduit_id`,
making policies bound to one conduit naturally deny calls on
another.

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
        # 3g typed the port (`conduit: str` -> `conduit_id: UUID`);
        # 3g still passes `policy.conduit_id` to evaluate so behavior
        # is unchanged. 3h flips to `conduit_id=conduit_id` (caller's
        # value) so policies bound to one conduit deny calls on
        # another via evaluate's existing conduit-mismatch check.
        _ = conduit_id

        policy = await load_policy(self._event_store, self._policy_id)
        if policy is None:
            _log.warning(
                "trust_authorize.policy_missing",
                policy_id=str(self._policy_id),
                principal_id=str(principal_id),
                command_name=command_name,
            )
            return Deny(
                reason=(
                    f"Configured TrustAuthorize policy {self._policy_id} not found in event store"
                )
            )

        result = evaluate(
            policy,
            principal_id=principal_id,
            command_name=command_name,
            conduit_id=policy.conduit_id,
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
