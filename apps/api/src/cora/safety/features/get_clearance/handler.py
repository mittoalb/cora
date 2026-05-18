"""Application handler for the `get_clearance` query slice.

Cross-BC query-handler shape (mirrored from `get_supply` / `get_actor`
/ `get_subject` / `get_family`):

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_clearance(...)            -> Clearance | None  (fold-on-read)
    3. return state                   -> caller maps None to 404 / isError

Returns the domain `Clearance`, not a DTO. The route layer maps to
`ClearanceResponse` and the MCP tool maps to its own structured output.

Query handlers do NOT emit `causation_id` log fields: queries have no
causation chain.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.safety.aggregates.clearance import Clearance, load_clearance
from cora.safety.errors import UnauthorizedError
from cora.safety.features.get_clearance.query import GetClearance

_QUERY_NAME = "GetClearance"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_clearance handler implements."""

    async def __call__(
        self,
        query: GetClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> Clearance | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_clearance handler closed over the shared deps."""

    async def handler(
        query: GetClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> Clearance | None:
        _log.info(
            "get_clearance.start",
            query_name=_QUERY_NAME,
            clearance_id=str(query.clearance_id),
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
                "get_clearance.denied",
                query_name=_QUERY_NAME,
                clearance_id=str(query.clearance_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        clearance = await load_clearance(deps.event_store, query.clearance_id)

        _log.info(
            "get_clearance.success",
            query_name=_QUERY_NAME,
            clearance_id=str(query.clearance_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=clearance is not None,
        )
        return clearance

    return handler
