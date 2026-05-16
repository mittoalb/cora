"""Application handler for the `list_campaigns` query slice.

Reads `proj_campaign_summary` directly via `deps.pool`. Five
optional filters (status / intent / lead_actor_id / subject_id /
tag), each via the declarative `$N::<type> IS NULL OR <column> = $N`
pattern (tag uses `$N = ANY(tags)` to leverage the per-column GIN
index; status uses ANY of an array since the default is the OPEN set
not a single value).

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(per `memory/project_authz_future.md`).

## status default = OPEN set (Planned + Active + Held)

Closed and Abandoned campaigns never appear in the default list view.
This pin is BC-design: the operator-facing list defaults to "what is
in progress / pending"; terminals must be requested explicitly. Pass
`status='all'` to opt into the full set, or pass an explicit status
value to narrow further.

Per Caution / Supply precedent the sentinel-to-array mapping happens
in Python before binding so the SQL stays parameterized.

## Filters intentionally deferred to 6i-c (Watch #10) / external_refs denorm

  - `has_run_id`: needs Run.campaign_id indexed scan on the Run
    projection. The Campaign projection only carries `run_count`
    (denorm size), not the UUID set. Watch item #10.
  - `external_ref_scheme` / `external_ref_id`: external_refs lives on
    the aggregate stream; reverse-query needs a per-ref denorm.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from cora.campaign.errors import UnauthorizedError
from cora.campaign.features.list_campaigns.query import ListCampaigns
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.projection import decode_cursor, encode_cursor

_QUERY_NAME = "ListCampaigns"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)

# The OPEN-set sentinel for the default status filter. None passed by
# the caller is mapped to this tuple before binding.
_OPEN_STATUSES: tuple[str, ...] = ("Planned", "Active", "Held")


@dataclass(frozen=True)
class CampaignSummaryItem:
    """One row from the campaign projection."""

    campaign_id: UUID
    name: str
    intent: str
    status: str
    lead_actor_id: UUID
    subject_id: UUID | None
    description: str | None
    tags: list[str]
    external_id: str | None
    run_count: int
    registered_at: datetime
    started_at: datetime | None
    last_status_changed_at: datetime | None
    last_status_reason: str | None


@dataclass(frozen=True)
class CampaignListPage:
    """A page of campaign summaries plus the cursor for the next page."""

    items: list[CampaignSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_campaigns handler implements."""

    async def __call__(
        self,
        query: ListCampaigns,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> CampaignListPage: ...


_SELECT_COLUMNS = """
SELECT campaign_id, name, intent, status, lead_actor_id, subject_id,
       description, tags, external_id, run_count, registered_at,
       started_at, last_status_changed_at, last_status_reason
"""

# $1 = limit (capped at 100)
# $2 = status_array TEXT[]  (None disables; default OPEN applied in Python)
# $3 = intent        TEXT
# $4 = lead_actor_id UUID
# $5 = subject_id    UUID
# $6 = tag           TEXT (matches via ANY(tags))
# $7 = cursor_at     TIMESTAMPTZ (cursor variant only)
# $8 = cursor_id     UUID         (cursor variant only)
_FILTER_CLAUSE = """
WHERE ($2::text[] IS NULL OR status = ANY($2::text[]))
  AND ($3::text IS NULL OR intent = $3)
  AND ($4::uuid IS NULL OR lead_actor_id = $4)
  AND ($5::uuid IS NULL OR subject_id = $5)
  AND ($6::text IS NULL OR $6 = ANY(tags))
"""

_LIST_NO_CURSOR_SQL = (
    _SELECT_COLUMNS
    + "FROM proj_campaign_summary\n"
    + _FILTER_CLAUSE
    + "ORDER BY registered_at ASC, campaign_id ASC\n"
    + "LIMIT $1"
)

_LIST_WITH_CURSOR_SQL = (
    _SELECT_COLUMNS
    + "FROM proj_campaign_summary\n"
    + _FILTER_CLAUSE
    + "  AND (registered_at, campaign_id) > ($7, $8)\n"
    + "ORDER BY registered_at ASC, campaign_id ASC\n"
    + "LIMIT $1"
)


def _resolve_status_filter(raw: str | None) -> tuple[str, ...] | None:
    """Resolve the status filter sentinel for SQL binding.

    None -> OPEN set (Planned + Active + Held): default hides Closed +
            Abandoned terminals from the list view.
    'all' -> None (disable the status filter; include every status).
    everything else -> single-element tuple with that status.
    """
    if raw is None:
        return _OPEN_STATUSES
    if raw == "all":
        return None
    return (raw,)


def bind(deps: Kernel) -> Handler:
    """Build a list_campaigns handler closed over the shared deps."""

    async def handler(
        query: ListCampaigns,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> CampaignListPage:
        status_array = _resolve_status_filter(query.status)

        _log.info(
            "list_campaigns.start",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            limit=query.limit,
            status=query.status,
            effective_status=status_array,
            intent=query.intent,
            lead_actor_id=str(query.lead_actor_id) if query.lead_actor_id else None,
            subject_id=str(query.subject_id) if query.subject_id else None,
            tag=query.tag,
            has_cursor=query.cursor is not None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "list_campaigns.denied",
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
                "list_campaigns.no_pool",
                query_name=_QUERY_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return CampaignListPage(items=[], next_cursor=None)

        # asyncpg expects list[str] for a text[] parameter; the None
        # sentinel disables the clause via the IS NULL guard above.
        status_bind = list(status_array) if status_array is not None else None

        async with deps.pool.acquire() as conn:
            if cursor_at is None:
                rows = await conn.fetch(
                    _LIST_NO_CURSOR_SQL,
                    query.limit + 1,
                    status_bind,
                    query.intent,
                    query.lead_actor_id,
                    query.subject_id,
                    query.tag,
                )
            else:
                rows = await conn.fetch(
                    _LIST_WITH_CURSOR_SQL,
                    query.limit + 1,
                    status_bind,
                    query.intent,
                    query.lead_actor_id,
                    query.subject_id,
                    query.tag,
                    cursor_at,
                    cursor_id,
                )

        has_more = len(rows) > query.limit
        kept = rows[: query.limit]
        items = [
            CampaignSummaryItem(
                campaign_id=row["campaign_id"],
                name=str(row["name"]),
                intent=str(row["intent"]),
                status=str(row["status"]),
                lead_actor_id=row["lead_actor_id"],
                subject_id=row["subject_id"],
                description=(str(row["description"]) if row["description"] is not None else None),
                tags=list(row["tags"]),
                external_id=(str(row["external_id"]) if row["external_id"] is not None else None),
                run_count=int(row["run_count"]),
                registered_at=row["registered_at"],
                started_at=row["started_at"],
                last_status_changed_at=row["last_status_changed_at"],
                last_status_reason=(
                    str(row["last_status_reason"])
                    if row["last_status_reason"] is not None
                    else None
                ),
            )
            for row in kept
        ]
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(
                created_at=last.registered_at,
                item_id=last.campaign_id,
            )

        _log.info(
            "list_campaigns.success",
            query_name=_QUERY_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            returned=len(items),
            has_next_page=next_cursor is not None,
        )
        return CampaignListPage(items=items, next_cursor=next_cursor)

    return handler


__all__ = [
    "CampaignListPage",
    "CampaignSummaryItem",
    "Handler",
    "bind",
]
