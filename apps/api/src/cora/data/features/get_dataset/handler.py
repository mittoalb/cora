"""Application handler for the `get_dataset` query slice.

Cross-BC query-handler shape (mirror of `get_subject`,
`get_actor`, `get_run`):

    1. authorize(principal_id, query_name, conduit) -> Allow | Deny
    2. load_dataset(...)            -> Dataset | None  (fold-on-read)
    3. return state                 -> caller maps None to 404 / isError

Returns the domain `Dataset`, not a DTO. The route layer maps to
`DatasetResponse` and the MCP tool maps to its own structured
output. Handlers stay in domain types so non-HTTP/MCP consumers
(other BCs, sagas, projections) get the rich object.

Query handlers do NOT emit `causation_id` log fields, queries have
no causation chain (they don't emit events that downstream commands
react to).
"""

from typing import Protocol
from uuid import UUID

from cora.data.aggregates.dataset import Dataset, load_dataset
from cora.data.errors import UnauthorizedError
from cora.data.features.get_dataset.query import GetDataset
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny

_QUERY_NAME = "GetDataset"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_dataset handler implements."""

    async def __call__(
        self,
        query: GetDataset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> Dataset | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_dataset handler closed over the shared deps."""

    async def handler(
        query: GetDataset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> Dataset | None:
        _log.info(
            "get_dataset.start",
            query_name=_QUERY_NAME,
            dataset_id=str(query.dataset_id),
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
                "get_dataset.denied",
                query_name=_QUERY_NAME,
                dataset_id=str(query.dataset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        dataset = await load_dataset(deps.event_store, query.dataset_id)

        _log.info(
            "get_dataset.success",
            query_name=_QUERY_NAME,
            dataset_id=str(query.dataset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=dataset is not None,
        )
        return dataset

    return handler
