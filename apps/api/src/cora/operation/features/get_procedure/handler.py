"""Application handler for the `get_procedure` query slice.

Cross-BC query-handler shape (Phase 2b precedent, mirrored from
`get_actor` / `get_subject` / `get_family` / `get_supply`):

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_procedure(...)             -> Procedure | None  (fold-on-read)
    3. return state                    -> caller maps None to 404 / isError

Returns the domain `Procedure`, not a DTO. The route layer maps to
`ProcedureResponse` and the MCP tool maps to its own structured
output. Handlers stay in domain types so non-HTTP/MCP consumers
(other BCs, sagas, projections) get the rich object.

Query handlers do NOT emit `causation_id` log fields -- queries
have no causation chain (they don't emit events that downstream
commands react to). Same convention as `get_family` /
`get_subject` / `get_supply`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.aggregates.procedure import Procedure, load_procedure
from cora.operation.errors import UnauthorizedError
from cora.operation.features.get_procedure.query import GetProcedure

_QUERY_NAME = "GetProcedure"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_procedure handler implements."""

    async def __call__(
        self,
        query: GetProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Procedure | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_procedure handler closed over the shared deps."""

    async def handler(
        query: GetProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Procedure | None:
        _log.info(
            "get_procedure.start",
            query_name=_QUERY_NAME,
            procedure_id=str(query.procedure_id),
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
                "get_procedure.denied",
                query_name=_QUERY_NAME,
                procedure_id=str(query.procedure_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        procedure = await load_procedure(deps.event_store, query.procedure_id)

        _log.info(
            "get_procedure.success",
            query_name=_QUERY_NAME,
            procedure_id=str(query.procedure_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=procedure is not None,
        )
        return procedure

    return handler
