"""Application handler for the `list_cautions` query slice.

Reads `proj_caution_summary` directly via `deps.pool`. Eight optional
filters (target_kind / target_id / category / severity / min_severity /
status / tag / author_actor_id), each via the declarative
`$N::<type> IS NULL OR <column> = $N` pattern (tag uses
`$N = ANY(tags)` to leverage the per-column GIN index;
min_severity uses a CASE-ordinal comparison; status defaults to
'Active' if omitted and "all" disables the filter).

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(per `memory/project_authz_future.md`).

## status default = 'Active' (anti-hook #6)

Retired and Superseded cautions never appear in the default list view.
This pin is BC-design: a forgotten Active filter would cause stale
warnings to surface in the operator UI. Pass `status='all'` to opt
into the full set, or pass an explicit status value to narrow further.

## min_severity ordinal mapping

`Notice / Caution / Warning` map to integers `0 / 1 / 2`. The handler
computes the int from the filter name before binding; the SQL CASE
expression on the projection row does the >= comparison. No new column
on the projection (the read-side derives the ordinal); same precedent
as the `risk_band` filter in `list_clearances` deferring its band
ordinal to the next slice that asks for it.

## propagate_to_children: NOT walked at query time (anti-hook Watch #8)

The projection's `propagate_to_children` column flows through to each
row unchanged. The handler does NOT walk Asset.parent_id chains to
include cautions inherited from parent assets. Future propagation lands
as either a denorm projection or a query-time join, whichever the
consumer asks for first.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from cora.caution.errors import UnauthorizedError
from cora.caution.features.list_cautions.query import ListCautions
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.projection import decode_cursor, encode_cursor

_QUERY_NAME = "ListCautions"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)

# Severity ordinal ladder: Notice (least) < Caution < Warning (most severe).
# Used to translate `min_severity` filter name into an integer bind so the
# SQL CASE expression can do a numeric `>=` comparison without a new column.
_SEVERITY_ORDINAL: dict[str, int] = {
    "Notice": 0,
    "Caution": 1,
    "Warning": 2,
}


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
    ) -> CautionListPage: ...


_SELECT_COLUMNS = """
SELECT caution_id, target_kind, target_id, category, severity, text, workaround,
       author_actor_id, tags, expires_at, propagate_to_children,
       status, parent_caution_id, superseded_by_caution_id, retired_reason,
       registered_at, last_status_changed_at
"""

# $1  = limit (capped at 100)
# $2  = target_kind        TEXT
# $3  = target_id          UUID
# $4  = category           TEXT
# $5  = severity           TEXT (exact match)
# $6  = min_severity_ord   INT (>= comparison via CASE)
# $7  = status             TEXT (None disables; default 'Active' applied in Python)
# $8  = tag                TEXT (matches via ANY(tags))
# $9  = author_actor_id    UUID
# $10 = cursor_at          TIMESTAMPTZ (cursor variant only)
# $11 = cursor_id          UUID         (cursor variant only)
_FILTER_CLAUSE = """
WHERE ($2::text IS NULL OR target_kind = $2)
  AND ($3::uuid IS NULL OR target_id = $3)
  AND ($4::text IS NULL OR category = $4)
  AND ($5::text IS NULL OR severity = $5)
  AND ($6::int IS NULL OR (CASE severity
           WHEN 'Notice' THEN 0
           WHEN 'Caution' THEN 1
           WHEN 'Warning' THEN 2
       END) >= $6)
  AND ($7::text IS NULL OR status = $7)
  AND ($8::text IS NULL OR $8 = ANY(tags))
  AND ($9::uuid IS NULL OR author_actor_id = $9)
"""

_LIST_NO_CURSOR_SQL = (
    _SELECT_COLUMNS
    + "FROM proj_caution_summary\n"
    + _FILTER_CLAUSE
    + "ORDER BY registered_at ASC, caution_id ASC\n"
    + "LIMIT $1"
)

_LIST_WITH_CURSOR_SQL = (
    _SELECT_COLUMNS
    + "FROM proj_caution_summary\n"
    + _FILTER_CLAUSE
    + "  AND (registered_at, caution_id) > ($10, $11)\n"
    + "ORDER BY registered_at ASC, caution_id ASC\n"
    + "LIMIT $1"
)


def _resolve_status_filter(raw: str | None) -> str | None:
    """Resolve the status filter sentinel for SQL binding.

    None -> 'Active' (default: hide Retired + Superseded from list view).
    'all' -> None (disable the status filter; include all 3 states).
    everything else -> pass through unchanged.
    """
    if raw is None:
        return "Active"
    if raw == "all":
        return None
    return raw


def _resolve_min_severity_ordinal(name: str | None) -> int | None:
    """Map a severity name to its ordinal (Notice=0, Caution=1, Warning=2).

    Returns None when no min_severity filter was passed.
    """
    if name is None:
        return None
    return _SEVERITY_ORDINAL[name]


def bind(deps: Kernel) -> Handler:
    """Build a list_cautions handler closed over the shared deps."""

    async def handler(
        query: ListCautions,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> CautionListPage:
        effective_status = _resolve_status_filter(query.status)
        min_severity_ord = _resolve_min_severity_ordinal(query.min_severity)

        _log.info(
            "list_cautions.start",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            limit=query.limit,
            target_kind=query.target_kind,
            target_id=str(query.target_id) if query.target_id else None,
            category=query.category,
            severity=query.severity,
            min_severity=query.min_severity,
            status=query.status,
            effective_status=effective_status,
            tag=query.tag,
            author_actor_id=str(query.author_actor_id) if query.author_actor_id else None,
            has_cursor=query.cursor is not None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "list_cautions.denied",
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
                "list_cautions.no_pool",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return CautionListPage(items=[], next_cursor=None)

        async with deps.pool.acquire() as conn:
            if cursor_at is None:
                rows = await conn.fetch(
                    _LIST_NO_CURSOR_SQL,
                    query.limit + 1,
                    query.target_kind,
                    query.target_id,
                    query.category,
                    query.severity,
                    min_severity_ord,
                    effective_status,
                    query.tag,
                    query.author_actor_id,
                )
            else:
                rows = await conn.fetch(
                    _LIST_WITH_CURSOR_SQL,
                    query.limit + 1,
                    query.target_kind,
                    query.target_id,
                    query.category,
                    query.severity,
                    min_severity_ord,
                    effective_status,
                    query.tag,
                    query.author_actor_id,
                    cursor_at,
                    cursor_id,
                )

        has_more = len(rows) > query.limit
        kept = rows[: query.limit]
        items = [
            CautionSummaryItem(
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
                retired_reason=(
                    str(row["retired_reason"]) if row["retired_reason"] is not None else None
                ),
                registered_at=row["registered_at"],
                last_status_changed_at=row["last_status_changed_at"],
            )
            for row in kept
        ]
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(
                created_at=last.registered_at,
                item_id=last.caution_id,
            )

        _log.info(
            "list_cautions.success",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            returned=len(items),
            has_next_page=next_cursor is not None,
        )
        return CautionListPage(items=items, next_cursor=next_cursor)

    return handler


__all__ = [
    "CautionListPage",
    "CautionSummaryItem",
    "Handler",
    "bind",
]
