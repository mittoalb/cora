"""Vertical slice for the `ListPermissions` query.

Enumerates a Policy's permitted commands for (principal, conduit).
Sibling to `check_permissions` (probe) — same Policy load, different
output shape (full set vs per-command rows).

    from cora.trust.features import list_permissions

    q = list_permissions.ListPermissions(
        policy_id=...,
        evaluated_principal_id=...,
        evaluated_conduit_id=...,
    )
    handler = list_permissions.bind(deps)
    result = await handler(q, principal_id=..., correlation_id=...)
    # result is None | PermissionListing

Design lock: `memory/project_permissions_query_design.md`.
"""

from cora.trust.features.list_permissions import tool
from cora.trust.features.list_permissions.handler import Handler, bind
from cora.trust.features.list_permissions.query import ListPermissions, PermissionListing
from cora.trust.features.list_permissions.route import router

__all__ = [
    "Handler",
    "ListPermissions",
    "PermissionListing",
    "bind",
    "router",
    "tool",
]
