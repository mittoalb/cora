"""Application handler for the `list_decisions` query slice.

Reads `proj_decision_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory. Three
optional filters (confidence_band + decision_rule + actor_id) plus
cursor pagination on `(created_at, decision_id)`.

`confidence` (the raw float) flows through to the result row;
`confidence_band` is returned in pre-computed string form (Low /
Medium / High / Certain, or null when confidence was not set).

BOLA: command-name gating only. Per-row scoping deferred until ReBAC.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.decision.errors import UnauthorizedError
from cora.decision.features.list_decisions.query import ListDecisions
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import ScalarFilter, make_list_query_handler
from cora.infrastructure.routing import NIL_SENTINEL_ID


@dataclass(frozen=True)
class DecisionSummaryItem:
    """One row from the decision projection."""

    decision_id: UUID
    actor_id: UUID
    decision_rule: str | None
    parent_id: UUID | None
    confidence: float | None
    confidence_band: str | None
    created_at: datetime


@dataclass(frozen=True)
class DecisionListPage:
    """A page of decision summaries plus the cursor for the next page."""

    items: list[DecisionSummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_decisions handler implements."""

    async def __call__(
        self,
        query: ListDecisions,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> DecisionListPage: ...


_SELECT_COLUMNS = (
    "decision_id, actor_id, decision_rule, parent_id, confidence, confidence_band, created_at"
)


def _row_to_item(row: Any) -> DecisionSummaryItem:
    return DecisionSummaryItem(
        decision_id=row["decision_id"],
        actor_id=row["actor_id"],
        decision_rule=str(row["decision_rule"]) if row["decision_rule"] is not None else None,
        parent_id=row["parent_id"],
        confidence=row["confidence"],
        confidence_band=(
            str(row["confidence_band"]) if row["confidence_band"] is not None else None
        ),
        created_at=row["created_at"],
    )


def _log_fields(query: ListDecisions) -> dict[str, Any]:
    return {
        "confidence_band": query.confidence_band,
        "decision_rule": query.decision_rule,
        "actor_id": str(query.actor_id) if query.actor_id else None,
    }


def bind(deps: Kernel) -> Handler:
    """Build a list_decisions handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListDecisions",
        log_prefix="list_decisions",
        unauthorized_error=UnauthorizedError,
        table="proj_decision_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="created_at",
        id_column="decision_id",
        filters=[
            ScalarFilter(attr="confidence_band"),
            ScalarFilter(attr="decision_rule"),
            ScalarFilter(attr="actor_id"),
        ],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.created_at,
        item_cursor_id=lambda item: item.decision_id,
        page_from=lambda items, next_cursor: DecisionListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "DecisionListPage",
    "DecisionSummaryItem",
    "Handler",
    "bind",
]
