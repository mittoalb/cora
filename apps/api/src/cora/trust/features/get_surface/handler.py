"""Application handler for the `get_surface` query slice."""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.trust.aggregates.surface import Surface, load_surface
from cora.trust.errors import UnauthorizedError
from cora.trust.features.get_surface.query import GetSurface

_QUERY_NAME = "GetSurface"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_surface handler implements."""

    async def __call__(
        self,
        query: GetSurface,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = _CONDUIT_DEFAULT_ID,
    ) -> Surface | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_surface handler closed over the shared deps."""

    async def handler(
        query: GetSurface,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = _CONDUIT_DEFAULT_ID,
    ) -> Surface | None:
        _log.info(
            "get_surface.start",
            query_name=_QUERY_NAME,
            surface_id=str(query.surface_id),
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
                "get_surface.denied",
                query_name=_QUERY_NAME,
                surface_id=str(query.surface_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        surface = await load_surface(deps.event_store, query.surface_id)

        _log.info(
            "get_surface.success",
            query_name=_QUERY_NAME,
            surface_id=str(query.surface_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=surface is not None,
        )
        return surface

    return handler
