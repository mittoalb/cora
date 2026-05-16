"""Application handler for the `get_caution` query slice.

Cross-BC query-handler shape (Phase 2b precedent, mirrored from
`get_supply` / `get_clearance`):

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_caution(...)             -> Caution | None  (fold-on-read)
    3. return state                  -> caller maps None to 404 / isError

Returns the domain `Caution`, not a DTO. The route layer maps to
`CautionResponse` and the MCP tool maps to its own structured output.
"""

from typing import Protocol
from uuid import UUID

from cora.caution.aggregates.caution import Caution, load_caution
from cora.caution.errors import UnauthorizedError
from cora.caution.features.get_caution.query import GetCaution
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny

_QUERY_NAME = "GetCaution"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_caution handler implements."""

    async def __call__(
        self,
        query: GetCaution,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> Caution | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_caution handler closed over the shared deps."""

    async def handler(
        query: GetCaution,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> Caution | None:
        _log.info(
            "get_caution.start",
            query_name=_QUERY_NAME,
            caution_id=str(query.caution_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "get_caution.denied",
                query_name=_QUERY_NAME,
                caution_id=str(query.caution_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        caution = await load_caution(deps.event_store, query.caution_id)

        _log.info(
            "get_caution.success",
            query_name=_QUERY_NAME,
            caution_id=str(query.caution_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=caution is not None,
        )
        return caution

    return handler
