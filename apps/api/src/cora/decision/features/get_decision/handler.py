"""Application handler for the `get_decision` query slice."""

from typing import Protocol
from uuid import UUID

from cora.decision.aggregates.decision import Decision, load_decision
from cora.decision.errors import UnauthorizedError
from cora.decision.features.get_decision.query import GetDecision
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "GetDecision"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_decision handler implements."""

    async def __call__(
        self,
        query: GetDecision,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Decision | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_decision handler closed over the shared deps."""

    async def handler(
        query: GetDecision,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Decision | None:
        _log.info(
            "get_decision.start",
            query_name=_QUERY_NAME,
            decision_id=str(query.decision_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        authz = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(authz, Deny):
            _log.info(
                "get_decision.denied",
                query_name=_QUERY_NAME,
                decision_id=str(query.decision_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=authz.reason,
            )
            raise UnauthorizedError(authz.reason)

        decision = await load_decision(deps.event_store, query.decision_id)

        _log.info(
            "get_decision.success",
            query_name=_QUERY_NAME,
            decision_id=str(query.decision_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=decision is not None,
        )
        return decision

    return handler
