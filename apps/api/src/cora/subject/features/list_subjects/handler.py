"""Application handler for the `list_subjects` query slice.

Reads `proj_subject_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory.
Single optional `status` filter plus cursor pagination on
`(created_at, subject_id)`.

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(see `memory/project_deferred.md`).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import ScalarFilter, make_list_query_handler
from cora.subject.errors import UnauthorizedError
from cora.subject.features.list_subjects.query import ListSubjects

_NIL_SENTINEL_ID = UUID(int=0)


@dataclass(frozen=True)
class SubjectSummaryItem:
    """One row from the subject projection."""

    subject_id: UUID
    name: str
    status: str
    created_at: datetime


@dataclass(frozen=True)
class SubjectListPage:
    """A page of subject summaries plus the cursor for the next page."""

    items: list[SubjectSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_subjects handler implements."""

    async def __call__(
        self,
        query: ListSubjects,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> SubjectListPage: ...


_SELECT_COLUMNS = "subject_id, name, status, created_at"


def _row_to_item(row: Any) -> SubjectSummaryItem:
    return SubjectSummaryItem(
        subject_id=row["subject_id"],
        name=str(row["name"]),
        status=str(row["status"]),
        created_at=row["created_at"],
    )


def _log_fields(query: ListSubjects) -> dict[str, Any]:
    return {"status": query.status}


def bind(deps: Kernel) -> Handler:
    """Build a list_subjects handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListSubjects",
        log_prefix="list_subjects",
        unauthorized_error=UnauthorizedError,
        table="proj_subject_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="created_at",
        id_column="subject_id",
        filters=[ScalarFilter(attr="status")],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.created_at,
        item_cursor_id=lambda item: item.subject_id,
        page_from=lambda items, next_cursor: SubjectListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "Handler",
    "SubjectListPage",
    "SubjectSummaryItem",
    "bind",
]
