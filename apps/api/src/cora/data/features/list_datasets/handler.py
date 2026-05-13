"""Application handler for the `list_datasets` query slice.

Reads `proj_data_dataset_summary` directly via `deps.pool`. Three
optional filters (status + producing_run_id + subject_id) plus
cursor pagination, using the `$N::text IS NULL OR column = $N`
declarative pattern.

`producing_run_id` and `subject_id` are nullable in the projection
(Datasets can exist without a producing Run or measured Subject per
Phase 7's cross-track validation). The filter SQL handles both the
"omit for any" and "match specific" cases.

BOLA: command-name gating only. Per-row scoping deferred until ReBAC.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from cora.data.errors import UnauthorizedError
from cora.data.features.list_datasets.query import ListDatasets
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.projection import decode_cursor, encode_cursor

_QUERY_NAME = "ListDatasets"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


@dataclass(frozen=True)
class DatasetSummaryItem:
    """One row from the dataset projection."""

    dataset_id: UUID
    name: str
    uri: str
    producing_run_id: UUID | None
    subject_id: UUID | None
    status: str
    created_at: datetime


@dataclass(frozen=True)
class DatasetListPage:
    """A page of dataset summaries plus the cursor for the next page."""

    items: list[DatasetSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_datasets handler implements."""

    async def __call__(
        self,
        query: ListDatasets,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> DatasetListPage: ...


_LIST_NO_CURSOR_SQL = """
SELECT dataset_id, name, uri, producing_run_id, subject_id, status, created_at
FROM proj_data_dataset_summary
WHERE ($2::text IS NULL OR status = $2)
  AND ($3::uuid IS NULL OR producing_run_id = $3)
  AND ($4::uuid IS NULL OR subject_id = $4)
ORDER BY created_at ASC, dataset_id ASC
LIMIT $1
"""

_LIST_WITH_CURSOR_SQL = """
SELECT dataset_id, name, uri, producing_run_id, subject_id, status, created_at
FROM proj_data_dataset_summary
WHERE ($2::text IS NULL OR status = $2)
  AND ($3::uuid IS NULL OR producing_run_id = $3)
  AND ($4::uuid IS NULL OR subject_id = $4)
  AND (created_at, dataset_id) > ($5, $6)
ORDER BY created_at ASC, dataset_id ASC
LIMIT $1
"""


def bind(deps: Kernel) -> Handler:
    """Build a list_datasets handler closed over the shared deps."""

    async def handler(
        query: ListDatasets,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> DatasetListPage:
        _log.info(
            "list_datasets.start",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            limit=query.limit,
            status=query.status,
            producing_run_id=str(query.producing_run_id) if query.producing_run_id else None,
            subject_id=str(query.subject_id) if query.subject_id else None,
            has_cursor=query.cursor is not None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "list_datasets.denied",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        cursor_at: datetime | None = None
        cursor_id: UUID | None = None
        if query.cursor is not None:
            cursor_at, cursor_id = decode_cursor(query.cursor)

        if deps.pool is None:
            _log.info(
                "list_datasets.no_pool",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return DatasetListPage(items=[], next_cursor=None)

        async with deps.pool.acquire() as conn:
            if cursor_at is None:
                rows = await conn.fetch(
                    _LIST_NO_CURSOR_SQL,
                    query.limit + 1,
                    query.status,
                    query.producing_run_id,
                    query.subject_id,
                )
            else:
                rows = await conn.fetch(
                    _LIST_WITH_CURSOR_SQL,
                    query.limit + 1,
                    query.status,
                    query.producing_run_id,
                    query.subject_id,
                    cursor_at,
                    cursor_id,
                )

        has_more = len(rows) > query.limit
        kept = rows[: query.limit]
        items = [
            DatasetSummaryItem(
                dataset_id=row["dataset_id"],
                name=str(row["name"]),
                uri=str(row["uri"]),
                producing_run_id=row["producing_run_id"],
                subject_id=row["subject_id"],
                status=str(row["status"]),
                created_at=row["created_at"],
            )
            for row in kept
        ]
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(
                created_at=last.created_at,
                item_id=last.dataset_id,
            )

        _log.info(
            "list_datasets.success",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            returned=len(items),
            has_next_page=next_cursor is not None,
        )
        return DatasetListPage(items=items, next_cursor=next_cursor)

    return handler


__all__ = [
    "DatasetListPage",
    "DatasetSummaryItem",
    "Handler",
    "bind",
]
