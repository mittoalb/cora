"""Application handler for the `list_campaigns` query slice.

Reads `proj_campaign_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory. Five
optional filters: three scalar (`intent` / `lead_actor_id` /
`subject_id`), one array-membership over the GIN-indexed `tags`
column, and one set-membership over the scalar `status` column
(`statuses` matches `status`). Cursor pagination on
`(registered_at, campaign_id)`.

User-facing UX (the `status` sentinel including 'all', the
default-to-OPEN-set behavior) lives at the route boundary per the
factory's growth-rule discipline (see
`cora.infrastructure.list_query` docstring "Growth rule"
section). The application handler sees only canonical filter
shapes: a list of acceptable status values, etc.

BOLA: command-name gating only. Per-row scoping deferred until ReBAC
(per `memory/project_authz_future.md`).

## Filters intentionally deferred (Watch #10) / external_refs denorm

  - `has_run_id`: needs Run.campaign_id indexed scan on the Run
    projection. The Campaign projection only carries `run_count`
    (denorm size), not the UUID set. Watch item #10.
  - `external_ref_scheme` / `external_ref_id`: external_refs lives on
    the aggregate stream; reverse-query needs a per-ref denorm.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.campaign.errors import UnauthorizedError
from cora.campaign.features.list_campaigns.query import ListCampaigns
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import (
    ArrayContainsFilter,
    ColumnInFilter,
    ScalarFilter,
    make_list_query_handler,
)
from cora.infrastructure.routing import NIL_SENTINEL_ID


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
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> CampaignListPage: ...


_SELECT_COLUMNS = (
    "campaign_id, name, intent, status, lead_actor_id, subject_id, "
    "description, tags, external_id, run_count, registered_at, "
    "started_at, last_status_changed_at, last_status_reason"
)


def _row_to_item(row: Any) -> CampaignSummaryItem:
    return CampaignSummaryItem(
        campaign_id=row["campaign_id"],
        name=str(row["name"]),
        intent=str(row["intent"]),
        status=str(row["status"]),
        lead_actor_id=row["lead_actor_id"],
        subject_id=row["subject_id"],
        description=str(row["description"]) if row["description"] is not None else None,
        tags=list(row["tags"]),
        external_id=str(row["external_id"]) if row["external_id"] is not None else None,
        run_count=int(row["run_count"]),
        registered_at=row["registered_at"],
        started_at=row["started_at"],
        last_status_changed_at=row["last_status_changed_at"],
        last_status_reason=(
            str(row["last_status_reason"]) if row["last_status_reason"] is not None else None
        ),
    )


def _log_fields(query: ListCampaigns) -> dict[str, Any]:
    return {
        "statuses": list(query.statuses) if query.statuses else None,
        "intent": query.intent,
        "lead_actor_id": str(query.lead_actor_id) if query.lead_actor_id else None,
        "subject_id": str(query.subject_id) if query.subject_id else None,
        "tag": query.tag,
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_campaigns handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListCampaigns",
        log_prefix="list_campaigns",
        unauthorized_error=UnauthorizedError,
        table="proj_campaign_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="registered_at",
        id_column="campaign_id",
        filters=[
            ColumnInFilter(attr="statuses", column="status"),
            ScalarFilter(attr="intent"),
            ScalarFilter(attr="lead_actor_id"),
            ScalarFilter(attr="subject_id"),
            ArrayContainsFilter(attr="tag", column="tags"),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.registered_at,
        item_cursor_id=lambda item: item.campaign_id,
        page_from=lambda items, next_cursor: CampaignListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "CampaignListPage",
    "CampaignSummaryItem",
    "Handler",
    "bind",
]
