"""PlanSummaryProjection: folds the Plan aggregate's
4 events into the `proj_recipe_plan_summary`
read model that backs `GET /plans`.

Subscribed events:
  - PlanDefined                  -> INSERT (status=Defined,
                                            version_tag=NULL,
                                            parameter_defaults_present=FALSE,
                                            practice_id + method_id from
                                            payload)
  - PlanVersioned                -> UPDATE status=Versioned + version_tag
                                            from payload
  - PlanDeprecated               -> UPDATE status=Deprecated (version_tag
                                            preserved on purpose; the
                                            audit trail of "last revised
                                            at version X before
                                            deprecation" stays visible)
  - PlanParameterDefaultsUpdated -> UPDATE parameter_defaults_present
                                            (TRUE if parameter_defaults is
                                            non-empty; FALSE if cleared
                                            via {}) (Phase 6g-b)

`practice_id` and `method_id` come from the genesis event and never
change (no event re-issues them), so the INSERT carries them and
later updates leave them alone. practice_id surfaces the cross-
aggregate filter ("show me all Plans using Practice X").

`parameter_defaults_present` is TRUE iff the latest
`PlanParameterDefaultsUpdated.parameter_defaults` payload was
non-empty; the dict content itself lives in the event stream
(loaded on demand, not projected to keep the summary table small).
Mirrors `MethodSummaryProjection.parameters_schema_present` shape
from 6g-a.

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
    (plan_id, name, practice_id, method_id, status, version_tag, created_at,
     parameter_defaults_present)
VALUES ($1, $2, $3, $4, 'Defined', NULL, $5, FALSE)
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

_UPDATE_PARAMETER_DEFAULTS_PRESENT_SQL = """
UPDATE proj_recipe_plan_summary
SET parameter_defaults_present = $2, updated_at = now()
WHERE plan_id = $1
"""


class PlanSummaryProjection:
    """Maintains the `proj_recipe_plan_summary` read model."""

    name = "proj_recipe_plan_summary"
    subscribed_event_types = frozenset(
        {
            "PlanDefined",
            "PlanVersioned",
            "PlanDeprecated",
            "PlanParameterDefaultsUpdated",
        }
    )

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
            case "PlanParameterDefaultsUpdated":
                # bool(...) on the dict: True iff non-empty. Clearing all
                # keys via merge_patch leaves an empty dict in the payload,
                # which flips the column back to FALSE.
                await conn.execute(
                    _UPDATE_PARAMETER_DEFAULTS_PRESENT_SQL,
                    UUID(event.payload["plan_id"]),
                    bool(event.payload.get("parameter_defaults")),
                )
            case _:
                pass


__all__ = ["PlanSummaryProjection"]
