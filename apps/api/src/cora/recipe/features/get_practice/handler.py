"""Application handler for the `get_practice` query slice.

Cross-BC query-handler shape mirroring `get_method` / `get_capability`
/ `get_subject` / `get_actor`:

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_practice(...)           -> Practice | None  (fold-on-read)
    3. return state                 -> caller maps None to 404 / isError

Returns the domain `Practice`, not a DTO. Query handlers do NOT
emit `causation_id` log fields.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.recipe.aggregates.practice import Practice, load_practice
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.get_practice.query import GetPractice

_QUERY_NAME = "GetPractice"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_practice handler implements."""

    async def __call__(
        self,
        query: GetPractice,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> Practice | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_practice handler closed over the shared deps."""

    async def handler(
        query: GetPractice,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> Practice | None:
        _log.info(
            "get_practice.start",
            query_name=_QUERY_NAME,
            practice_id=str(query.practice_id),
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
                "get_practice.denied",
                query_name=_QUERY_NAME,
                practice_id=str(query.practice_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        practice = await load_practice(deps.event_store, query.practice_id)

        _log.info(
            "get_practice.success",
            query_name=_QUERY_NAME,
            practice_id=str(query.practice_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=practice is not None,
        )
        return practice

    return handler
