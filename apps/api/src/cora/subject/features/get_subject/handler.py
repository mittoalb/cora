"""Application handler for the `get_subject` query slice.

Cross-BC query-handler shape, mirrored from `get_actor`:

    1. authorize(principal_id, query_name, conduit) -> Allow | Deny
       (under AllowAllAuthorize this is currently a no-op; the call
       site is in place so a future Trust BC swap is mechanical
       per handler instead of a sweep that risks missing handlers.)
    2. load_subject(...)            -> Subject | None  (fold-on-read)
    3. return state                 -> caller maps None to 404 / isError

Returns the domain `Subject`, not a DTO. The route layer maps to
`SubjectResponse` and the MCP tool maps to its own structured output.
Handlers stay in domain types so non-HTTP/MCP consumers (other BCs,
sagas, projections) get the rich object.

Query handlers do NOT emit `causation_id` log fields — queries have
no causation chain (they don't emit events that downstream commands
react to). Same convention as `get_actor`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.subject.aggregates.subject import Subject, load_subject
from cora.subject.errors import UnauthorizedError
from cora.subject.features.get_subject.query import GetSubject

_QUERY_NAME = "GetSubject"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_subject handler implements."""

    async def __call__(
        self,
        query: GetSubject,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Subject | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_subject handler closed over the shared deps."""

    async def handler(
        query: GetSubject,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Subject | None:
        _log.info(
            "get_subject.start",
            query_name=_QUERY_NAME,
            subject_id=str(query.subject_id),
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
                "get_subject.denied",
                query_name=_QUERY_NAME,
                subject_id=str(query.subject_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        subject = await load_subject(deps.event_store, query.subject_id)

        _log.info(
            "get_subject.success",
            query_name=_QUERY_NAME,
            subject_id=str(query.subject_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=subject is not None,
        )
        return subject

    return handler
