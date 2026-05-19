"""Application handler for the `get_capability` query slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.recipe.aggregates.capability import Capability, load_capability
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.get_capability.query import GetCapability

_QUERY_NAME = "GetCapability"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_capability handler implements."""

    async def __call__(
        self,
        query: GetCapability,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = _CONDUIT_DEFAULT_ID,
    ) -> Capability | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_capability handler closed over the shared deps."""

    async def handler(
        query: GetCapability,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = _CONDUIT_DEFAULT_ID,
    ) -> Capability | None:
        _log.info(
            "get_capability.start",
            query_name=_QUERY_NAME,
            capability_id=str(query.capability_id),
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
                "get_capability.denied",
                query_name=_QUERY_NAME,
                capability_id=str(query.capability_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        capability = await load_capability(deps.event_store, query.capability_id)

        _log.info(
            "get_capability.success",
            query_name=_QUERY_NAME,
            capability_id=str(query.capability_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=capability is not None,
        )
        return capability

    return handler
