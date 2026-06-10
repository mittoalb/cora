"""Application handler for the `get_clearance_template` query slice.

Cross-BC query-handler shape, mirrored from `get_family`; reads the
ClearanceTemplate aggregate via event store load. No projection-sourced
timestamps (unlike Family Path C); lifecycle timestamps are embedded
in the ClearanceTemplate state itself (defined_at, defined_by).

Query handlers do NOT emit `causation_id` log fields  --  queries
have no causation chain (they don't emit events that downstream
commands react to). Same convention as `get_actor` / `get_subject`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplate,
    load_clearance_template,
)
from cora.safety.errors import UnauthorizedError
from cora.safety.features.get_clearance_template.query import GetClearanceTemplate

_QUERY_NAME = "GetClearanceTemplate"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_clearance_template handler implements."""

    async def __call__(
        self,
        query: GetClearanceTemplate,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ClearanceTemplate | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_clearance_template handler closed over the shared deps."""

    async def handler(
        query: GetClearanceTemplate,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ClearanceTemplate | None:
        _log.info(
            "get_clearance_template.start",
            query_name=_QUERY_NAME,
            template_id=str(query.template_id),
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
                "get_clearance_template.denied",
                query_name=_QUERY_NAME,
                template_id=str(query.template_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        template = await load_clearance_template(deps.event_store, query.template_id)
        if template is None:
            _log.info(
                "get_clearance_template.success",
                query_name=_QUERY_NAME,
                template_id=str(query.template_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None

        _log.info(
            "get_clearance_template.success",
            query_name=_QUERY_NAME,
            template_id=str(query.template_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
        )
        return template

    return handler
