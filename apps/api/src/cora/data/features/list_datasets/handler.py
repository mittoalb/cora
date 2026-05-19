"""Application handler for the `list_datasets` query slice.

Reads `proj_data_dataset_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory.
Three optional filters (status + producing_run_id + subject_id)
plus cursor pagination on `(created_at, dataset_id)`.

`producing_run_id` and `subject_id` are nullable in the projection
(Datasets can exist without a producing Run or measured Subject per
Phase 7's cross-track validation).

BOLA: command-name gating only. Per-row scoping deferred until ReBAC.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.data.errors import UnauthorizedError
from cora.data.features.list_datasets.query import ListDatasets
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import ScalarFilter, make_list_query_handler

_NIL_SENTINEL_ID = UUID(int=0)


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
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> DatasetListPage: ...


_SELECT_COLUMNS = "dataset_id, name, uri, producing_run_id, subject_id, status, created_at"


def _row_to_item(row: Any) -> DatasetSummaryItem:
    return DatasetSummaryItem(
        dataset_id=row["dataset_id"],
        name=str(row["name"]),
        uri=str(row["uri"]),
        producing_run_id=row["producing_run_id"],
        subject_id=row["subject_id"],
        status=str(row["status"]),
        created_at=row["created_at"],
    )


def _log_fields(query: ListDatasets) -> dict[str, Any]:
    return {
        "status": query.status,
        "producing_run_id": str(query.producing_run_id) if query.producing_run_id else None,
        "subject_id": str(query.subject_id) if query.subject_id else None,
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_datasets handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListDatasets",
        log_prefix="list_datasets",
        unauthorized_error=UnauthorizedError,
        table="proj_data_dataset_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="created_at",
        id_column="dataset_id",
        filters=[
            ScalarFilter(attr="status"),
            ScalarFilter(attr="producing_run_id"),
            ScalarFilter(attr="subject_id"),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.created_at,
        item_cursor_id=lambda item: item.dataset_id,
        page_from=lambda items, next_cursor: DatasetListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "DatasetListPage",
    "DatasetSummaryItem",
    "Handler",
    "bind",
]
