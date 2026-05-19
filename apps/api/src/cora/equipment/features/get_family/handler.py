"""Application handler for the `get_family` query slice.

Cross-BC query-handler shape (Phase 2b precedent, mirrored from
`get_actor` / `get_subject`):

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_family(...)         -> Family | None  (fold-on-read)
    3. return state                 -> caller maps None to 404 / isError

Returns the domain `Family`, not a DTO. The route layer maps
to `FamilyResponse` and the MCP tool maps to its own
structured output. Handlers stay in domain types so non-HTTP/MCP
consumers (other BCs, sagas, projections) get the rich object.

Query handlers do NOT emit `causation_id` log fields — queries
have no causation chain (they don't emit events that downstream
commands react to). Same convention as `get_actor` / `get_subject`.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.family import Family, load_family
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.get_family.query import GetFamily
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "GetFamily"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_family handler implements."""

    async def __call__(
        self,
        query: GetFamily,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Family | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_family handler closed over the shared deps."""

    async def handler(
        query: GetFamily,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Family | None:
        _log.info(
            "get_family.start",
            query_name=_QUERY_NAME,
            family_id=str(query.family_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "get_family.denied",
                query_name=_QUERY_NAME,
                family_id=str(query.family_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        family = await load_family(deps.event_store, query.family_id)

        _log.info(
            "get_family.success",
            query_name=_QUERY_NAME,
            family_id=str(query.family_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=family is not None,
        )
        return family

    return handler
