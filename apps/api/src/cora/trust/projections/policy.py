"""PolicySummaryProjection: folds the PolicyDefined event into the
`proj_trust_policy_summary` read model that backs `GET /policies`.

Subscribed events:
  - PolicyDefined  -> INSERT (id + name + conduit_id + occurred_at)

The list-typed `permitted_principals` and `permitted_commands`
payload fields are intentionally NOT projected: they are list-shaped
and a future `proj_trust_policy_principals` join projection covers
"list policies allowing Principal X" if that use case crystallizes
(analog to the deferred `proj_recipe_method_capabilities` join
documented in recipe/projections/method.py).

Policy is immutable-once-defined for Phase 8e-8 (lifecycle
Drafted -> Approved -> Active -> Superseded per BC-map deferred
per the additive-state pattern in policy/state.py).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_POLICY_SQL = """
INSERT INTO proj_trust_policy_summary
    (policy_id, name, conduit_id, created_at)
VALUES ($1, $2, $3, $4)
ON CONFLICT (policy_id) DO NOTHING
"""


class PolicySummaryProjection:
    """Maintains the `proj_trust_policy_summary` read model."""

    name = "proj_trust_policy_summary"
    subscribed_event_types = frozenset({"PolicyDefined"})

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type != "PolicyDefined":
            return
        payload = event.payload
        await conn.execute(
            _INSERT_POLICY_SQL,
            UUID(payload["policy_id"]),
            payload["name"],
            UUID(payload["conduit_id"]),
            datetime.fromisoformat(payload["occurred_at"]),
        )


__all__ = ["PolicySummaryProjection"]
