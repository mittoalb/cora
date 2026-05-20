"""Application handler for the `get_run` query slice.

Cross-BC query-handler shape mirroring `get_plan` / `get_practice`
/ `get_method` / `get_family` / `get_subject` / `get_actor`.

Returns the domain `Run`, not a DTO. The route + tool layers do
their own DTO mapping (primitives only).

Query handlers do NOT emit `causation_id` log fields.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import Run, load_run
from cora.run.errors import UnauthorizedError
from cora.run.features.get_run.query import GetRun

_QUERY_NAME = "GetRun"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_run handler implements."""

    async def __call__(
        self,
        query: GetRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Run | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_run handler closed over the shared deps."""

    async def handler(
        query: GetRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Run | None:
        _log.info(
            "get_run.start",
            query_name=_QUERY_NAME,
            run_id=str(query.run_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "get_run.denied",
                query_name=_QUERY_NAME,
                run_id=str(query.run_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        run = await load_run(deps.event_store, query.run_id)

        _log.info(
            "get_run.success",
            query_name=_QUERY_NAME,
            run_id=str(query.run_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=run is not None,
        )
        return run

    return handler
