"""PlanSummaryProjection: folds the Plan aggregate's
3 lifecycle events into the `proj_recipe_plan_summary`
read model that backs `GET /plans`.

Subscribed events:
  - PlanDefined    -> INSERT (status=Defined, version_tag=NULL,
                              practice_id + method_id from payload)
  - PlanVersioned  -> UPDATE status=Versioned + version_tag from payload
  - PlanDeprecated -> UPDATE status=Deprecated (version_tag preserved)

`practice_id` and `method_id` come from the genesis event and never
change (no event re-issues them), so the INSERT carries them and
later updates leave them alone. practice_id surfaces the cross-
aggregate filter ("show me all Plans using Practice X").

`asset_ids` from the genesis payload is intentionally NOT in this
projection: it's a list, the keyset+filter shape doesn't need it,
and a future `proj_recipe_plan_assets` join projection can carry
it when use cases demand "all plans using Asset X". Same precedent
as Method.needs_capabilities.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_PLAN_SQL = """
INSERT INTO proj_recipe_plan_summary
    (plan_id, name, practice_id, method_id, status, version_tag, created_at)
VALUES ($1, $2, $3, $4, 'Defined', NULL, $5)
ON CONFLICT (plan_id) DO NOTHING
"""

_UPDATE_VERSIONED_SQL = """
UPDATE proj_recipe_plan_summary
SET status = 'Versioned', version_tag = $2, updated_at = now()
WHERE plan_id = $1
"""

_UPDATE_DEPRECATED_SQL = """
UPDATE proj_recipe_plan_summary
SET status = 'Deprecated', updated_at = now()
WHERE plan_id = $1
"""


class PlanSummaryProjection:
    """Maintains the `proj_recipe_plan_summary` read model."""

    name = "proj_recipe_plan_summary"
    subscribed_event_types = frozenset({"PlanDefined", "PlanVersioned", "PlanDeprecated"})

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "PlanDefined":
                await conn.execute(
                    _INSERT_PLAN_SQL,
                    UUID(event.payload["plan_id"]),
                    event.payload["name"],
                    UUID(event.payload["practice_id"]),
                    UUID(event.payload["method_id"]),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "PlanVersioned":
                await conn.execute(
                    _UPDATE_VERSIONED_SQL,
                    UUID(event.payload["plan_id"]),
                    event.payload["version_tag"],
                )
            case "PlanDeprecated":
                await conn.execute(
                    _UPDATE_DEPRECATED_SQL,
                    UUID(event.payload["plan_id"]),
                )
            case _:
                pass


__all__ = ["PlanSummaryProjection"]
