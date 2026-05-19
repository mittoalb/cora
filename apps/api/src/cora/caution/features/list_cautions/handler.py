"""Application handler for the `list_cautions` query slice.

Reads `proj_caution_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory. Seven
optional filters: five scalar (`target_kind` / `target_id` /
`category` / `tag` / `author_actor_id`) plus two set-membership
over scalar columns (`severities` matches `severity`, `statuses`
matches `status`). Cursor pagination on `(registered_at, caution_id)`.

User-facing UX (the `min_severity` ladder, the default-to-Active
behavior, the `?status=all` opt-in) lives at the route boundary
per the factory's growth-rule discipline (see
`cora.infrastructure.list_query` docstring "Growth rule"
section). The application handler sees only canonical filter
shapes: a list of acceptable severity values, a list of
acceptable status values.

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(per `memory/project_authz_future.md`).

## propagate_to_children: NOT walked at query time

The projection's `propagate_to_children` column flows through to each
row unchanged. The handler does NOT walk Asset.parent_id chains to
include cautions inherited from parent assets. Future propagation lands
as either a denorm projection or a query-time join, whichever the
consumer asks for first.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.caution.errors import UnauthorizedError
from cora.caution.features.list_cautions.query import ListCautions
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import (
    ArrayContainsFilter,
    ColumnInFilter,
    ScalarFilter,
    make_list_query_handler,
)
from cora.infrastructure.routing import NIL_SENTINEL_ID


@dataclass(frozen=True)
class CautionSummaryItem:
    """One row from the caution projection."""

    caution_id: UUID
    target_kind: str
    target_id: UUID
    category: str
    severity: str
    text: str
    workaround: str
    author_actor_id: UUID
    tags: list[str]
    expires_at: datetime | None
    propagate_to_children: bool
    status: str
    parent_caution_id: UUID | None
    superseded_by_caution_id: UUID | None
    retired_reason: str | None
    registered_at: datetime
    last_status_changed_at: datetime | None


@dataclass(frozen=True)
class CautionListPage:
    """A page of caution summaries plus the cursor for the next page."""

    items: list[CautionSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_cautions handler implements."""

    async def __call__(
        self,
        query: ListCautions,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> CautionListPage: ...


_SELECT_COLUMNS = (
    "caution_id, target_kind, target_id, category, severity, text, workaround, "
    "author_actor_id, tags, expires_at, propagate_to_children, "
    "status, parent_caution_id, superseded_by_caution_id, retired_reason, "
    "registered_at, last_status_changed_at"
)


def _row_to_item(row: Any) -> CautionSummaryItem:
    return CautionSummaryItem(
        caution_id=row["caution_id"],
        target_kind=str(row["target_kind"]),
        target_id=row["target_id"],
        category=str(row["category"]),
        severity=str(row["severity"]),
        text=str(row["text"]),
        workaround=str(row["workaround"]),
        author_actor_id=row["author_actor_id"],
        tags=list(row["tags"]),
        expires_at=row["expires_at"],
        propagate_to_children=bool(row["propagate_to_children"]),
        status=str(row["status"]),
        parent_caution_id=row["parent_caution_id"],
        superseded_by_caution_id=row["superseded_by_caution_id"],
        retired_reason=(str(row["retired_reason"]) if row["retired_reason"] is not None else None),
        registered_at=row["registered_at"],
        last_status_changed_at=row["last_status_changed_at"],
    )


def _log_fields(query: ListCautions) -> dict[str, Any]:
    return {
        "target_kind": query.target_kind,
        "target_id": str(query.target_id) if query.target_id else None,
        "category": query.category,
        "severities": list(query.severities) if query.severities else None,
        "statuses": list(query.statuses) if query.statuses else None,
        "tag": query.tag,
        "author_actor_id": (str(query.author_actor_id) if query.author_actor_id else None),
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_cautions handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListCautions",
        log_prefix="list_cautions",
        unauthorized_error=UnauthorizedError,
        table="proj_caution_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="registered_at",
        id_column="caution_id",
        filters=[
            ScalarFilter(attr="target_kind"),
            ScalarFilter(attr="target_id"),
            ScalarFilter(attr="category"),
            ColumnInFilter(attr="severities", column="severity"),
            ColumnInFilter(attr="statuses", column="status"),
            ArrayContainsFilter(attr="tag", column="tags"),
            ScalarFilter(attr="author_actor_id"),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.registered_at,
        item_cursor_id=lambda item: item.caution_id,
        page_from=lambda items, next_cursor: CautionListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "CautionListPage",
    "CautionSummaryItem",
    "Handler",
    "bind",
]
