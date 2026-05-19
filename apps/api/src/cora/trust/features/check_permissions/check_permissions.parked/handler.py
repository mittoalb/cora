"""Application handler for the `check_permissions` query slice.

Mirrors `evaluate_policy.handler` but iterates over a tuple of
commands, calling `evaluate(policy, ...)` per command. Returns
`list[PermissionCheck] | None` — None when the Policy doesn't exist
(route maps to 404).

Per the design lock (anti-hook AH3): this handler deliberately does
NOT route through `deps.authorize` to invoke `TrustAuthorize` for
the probe answer — it loads the Policy and calls the pure
`evaluate(...)` function directly. That keeps probes off the
ConduitTraversal logbook (probes are not real calls).

Caller authz (gating who can call the probe) still goes through
`deps.authorize` — same shape as `evaluate_policy`. Today's
permitted-principal-and-command checks are unchanged.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Allow, Deny
from cora.trust.aggregates.policy import evaluate, load_policy
from cora.trust.errors import UnauthorizedError
from cora.trust.features.check_permissions.query import CheckPermissions, PermissionCheck

_QUERY_NAME = "CheckPermissions"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every check_permissions handler implements."""

    async def __call__(
        self,
        query: CheckPermissions,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = _CONDUIT_DEFAULT_ID,
    ) -> list[PermissionCheck] | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a check_permissions handler closed over the shared deps."""

    async def handler(
        query: CheckPermissions,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = _CONDUIT_DEFAULT_ID,
    ) -> list[PermissionCheck] | None:
        _log.info(
            "check_permissions.start",
            query_name=_QUERY_NAME,
            policy_id=str(query.policy_id),
            evaluated_principal_id=str(query.evaluated_principal_id),
            command_count=len(query.evaluated_commands),
            on_behalf=query.evaluated_principal_id != principal_id,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,

            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "check_permissions.denied",
                query_name=_QUERY_NAME,
                policy_id=str(query.policy_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        policy = await load_policy(deps.event_store, query.policy_id)
        if policy is None:
            _log.info(
                "check_permissions.success",
                query_name=_QUERY_NAME,
                policy_id=str(query.policy_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None

        results: list[PermissionCheck] = []
        for command in query.evaluated_commands:
            result = evaluate(
                policy,
                principal_id=query.evaluated_principal_id,
                command_name=command,
                conduit_id=query.evaluated_conduit_id,
            )
            if isinstance(result, Allow):
                results.append(PermissionCheck(command=command, decision="allow", reason=None))
            else:
                # Narrowed to Deny via the Allow|Deny union exhaustiveness.
                assert isinstance(result, Deny)
                results.append(
                    PermissionCheck(command=command, decision="deny", reason=result.reason)
                )

        allow_count = sum(1 for r in results if r.decision == "allow")
        _log.info(
            "check_permissions.success",
            query_name=_QUERY_NAME,
            policy_id=str(query.policy_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
            command_count=len(results),
            allow_count=allow_count,
            deny_count=len(results) - allow_count,
        )
        return results

    return handler
