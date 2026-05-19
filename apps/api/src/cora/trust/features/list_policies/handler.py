"""Application handler for the `list_policies` query slice.

Reads `proj_trust_policy_summary` via the cross-BC
`infrastructure.list_query.make_list_query_handler` factory.
Single optional `conduit_id` filter plus cursor pagination on
`(created_at, policy_id)`.

The list-typed `permitted_principals` and `permitted_commands`
fields are NOT in the projection (and therefore not in the result
row); a future `proj_trust_policy_principals` join projection will
cover "list policies allowing Principal X" if that use case
crystallizes.

BOLA: command-name gating only. Per-row scoping deferred until ReBAC.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import ScalarFilter, make_list_query_handler
from cora.trust.errors import UnauthorizedError
from cora.trust.features.list_policies.query import ListPolicies

_NIL_SENTINEL_ID = UUID(int=0)


@dataclass(frozen=True)
class PolicySummaryItem:
    """One row from the policy projection."""

    policy_id: UUID
    name: str
    conduit_id: UUID
    created_at: datetime


@dataclass(frozen=True)
class PolicyListPage:
    """A page of policy summaries plus the cursor for the next page."""

    items: list[PolicySummaryItem]
    next_cursor: str | None


class Handler(Protocol):
    """Callable interface every list_policies handler implements."""

    async def __call__(
        self,
        query: ListPolicies,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> PolicyListPage: ...


_SELECT_COLUMNS = "policy_id, name, conduit_id, created_at"


def _row_to_item(row: Any) -> PolicySummaryItem:
    return PolicySummaryItem(
        policy_id=row["policy_id"],
        name=str(row["name"]),
        conduit_id=row["conduit_id"],
        created_at=row["created_at"],
    )


def _log_fields(query: ListPolicies) -> dict[str, Any]:
    return {"conduit_id": str(query.conduit_id) if query.conduit_id else None}


def bind(deps: Kernel) -> Handler:
    """Build a list_policies handler closed over the shared deps."""
    return make_list_query_handler(
        deps,
        query_name="ListPolicies",
        log_prefix="list_policies",
        unauthorized_error=UnauthorizedError,
        table="proj_trust_policy_summary",
        select_columns=_SELECT_COLUMNS,
        time_column="created_at",
        id_column="policy_id",
        filters=[ScalarFilter(attr="conduit_id")],
        row_to_item=_row_to_item,
        item_cursor_at=lambda item: item.created_at,
        item_cursor_id=lambda item: item.policy_id,
        page_from=lambda items, next_cursor: PolicyListPage(items=items, next_cursor=next_cursor),
        extract_log_fields=_log_fields,
    )


__all__ = [
    "Handler",
    "PolicyListPage",
    "PolicySummaryItem",
    "bind",
]
