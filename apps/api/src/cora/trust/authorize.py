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
- One policy per deployment (set via `Settings.trust_policy_id`)
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

Operational consequence: deployments wire `Settings.trust_policy_id`
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

    1. Start with `trust_policy_id` unset (AllowAllAuthorize).
    2. `POST /policies` with a permissive policy; record the id.
    3. Restart with `trust_policy_id` = that id.

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

## Phase 6f-5a: optional traversal entry emission

When constructed with a `TraversalStore`, every Allow / Deny
decision additionally writes one `ConduitTraversal` entry row
to the per-Conduit traversals logbook. This is the per-Conduit
authz audit log — every command that traverses a Conduit is
captured with actor, command, decision, reason, and timestamps.

Wiring is opt-in (constructor param defaults to None) so existing
test paths and the AllowAllAuthorize fallback don't accumulate
entries. When `traversals_store` is provided, `clock` and
`id_generator` are required (for `occurred_at` and `event_id`); the
constructor enforces this so missed wiring fails loud at app
startup, not at the first authz call.

Logbook id resolution: TrustAuthorize loads the target Conduit
aggregate via `load_conduit` and reads `conduit.logbooks[
LOGBOOK_KIND_TRAVERSALS]`. The Conduit stream is short (genesis +
logbook-open, ~handful of events) so per-call fold cost is small;
per-process caching keyed on `conduit_id` is the natural future
optimization. If the Conduit doesn't exist (typical for
`UUID(int=0)` sentinel until conduit-routing lands) or has no
traversals logbook open, the entry write is silently skipped with
a warn log — the authz decision itself is unaffected.

`correlation_id` for the entry row comes from
`current_correlation_id()` (the active OTel span's trace_id encoded
as a UUID); same source the calling handler uses for its event
envelope, so entry rows correlate naturally with the events that
triggered them.
"""

from uuid import UUID

from cora.infrastructure.logging import get_logger
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.ports import (
    Allow,
    AuthzResult,
    Clock,
    Deny,
    EventStore,
    IdGenerator,
)
from cora.trust.aggregates.conduit import LOGBOOK_KIND_TRAVERSALS, load_conduit
from cora.trust.aggregates.conduit.entries import (
    ConduitTraversal,
    TraversalDecision,
    TraversalStore,
)
from cora.trust.aggregates.policy import evaluate, load_policy

_log = get_logger(__name__)


class TrustAuthorize:
    """Authorize port adapter that gates via a single configured Policy."""

    def __init__(
        self,
        event_store: EventStore,
        *,
        policy_id: UUID,
        traversals_store: TraversalStore | None = None,
        clock: Clock | None = None,
        id_generator: IdGenerator | None = None,
    ) -> None:
        if traversals_store is not None and (clock is None or id_generator is None):
            msg = (
                "TrustAuthorize: traversals_store requires both clock and id_generator to be wired"
            )
            raise ValueError(msg)
        self._event_store = event_store
        self._policy_id = policy_id
        self._traversals_store = traversals_store
        self._clock = clock
        self._id_generator = id_generator

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
            result: AuthzResult = Deny(
                reason=(
                    f"Configured TrustAuthorize policy {self._policy_id} not found in event store"
                )
            )
        else:
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

        if self._traversals_store is not None:
            await self._emit_traversal(
                principal_id=principal_id,
                command_name=command_name,
                conduit_id=conduit_id,
                result=result,
            )

        return result

    async def _emit_traversal(
        self,
        *,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        result: AuthzResult,
    ) -> None:
        """Best-effort write of one ConduitTraversal entry per call.

        Skipped silently with a warn log if the Conduit doesn't exist
        or has no currently-open traversals logbook. The authz
        decision itself is unaffected.
        """
        # Type-narrowed: __init__ enforces that these are non-None
        # whenever traversals_store is set.
        assert self._traversals_store is not None
        assert self._clock is not None
        assert self._id_generator is not None

        conduit = await load_conduit(self._event_store, conduit_id)
        if conduit is None:
            _log.warning(
                "trust_authorize.skip_traversal",
                conduit_id=str(conduit_id),
                reason="conduit_not_found",
            )
            return
        logbook_id = conduit.logbooks.get(LOGBOOK_KIND_TRAVERSALS)
        if logbook_id is None:
            _log.warning(
                "trust_authorize.skip_traversal",
                conduit_id=str(conduit_id),
                reason="no_open_traversals_logbook",
            )
            return

        decision_str: TraversalDecision = "Allow" if isinstance(result, Allow) else "Deny"
        reason = result.reason if isinstance(result, Deny) else None

        await self._traversals_store.append(
            [
                ConduitTraversal(
                    event_id=self._id_generator.new_id(),
                    conduit_id=conduit_id,
                    logbook_id=logbook_id,
                    actor_id=principal_id,
                    command_name=command_name,
                    decision=decision_str,
                    reason=reason,
                    correlation_id=current_correlation_id(),
                    causation_id=None,
                    occurred_at=self._clock.now(),
                )
            ]
        )
