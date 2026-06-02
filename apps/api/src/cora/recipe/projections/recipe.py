"""RecipeSummaryProjection: folds the Recipe aggregate's lifecycle
events into `proj_recipe_recipe_summary`.

Subscribed events:
  - RecipeDefined    -> INSERT (status=Defined, version=NULL,
                                replaced_by_recipe_id=NULL,
                                steps_count from payload)
  - RecipeVersioned  -> UPDATE status=Versioned + version_tag +
                                REFRESH steps_count
                                (a new version IS a new declaration;
                                 steps replace wholesale)
  - RecipeDeprecated -> UPDATE status=Deprecated +
                                replaced_by_recipe_id
                                (steps + capability_id PRESERVED for audit)

All branches idempotent. `version_tag` lands ONLY on Versioned
(Defined INSERT leaves it NULL and Deprecated UPDATE doesn't touch
it). `steps_count` is the denormalized number of `RecipeStep`s in
the latest event's payload; the steps themselves live in the event
stream per [[project-pg-smart-logic-observation]] to keep the summary
table small.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_RECIPE_SQL = """
INSERT INTO proj_recipe_recipe_summary
    (recipe_id, name, capability_id, status, version_tag,
     steps_count, replaced_by_recipe_id, created_at)
VALUES ($1, $2, $3, 'Defined', NULL, $4, NULL, $5)
ON CONFLICT (recipe_id) DO NOTHING
"""

_UPDATE_VERSIONED_SQL = """
UPDATE proj_recipe_recipe_summary
SET status = 'Versioned',
    version_tag = $2,
    steps_count = $3,
    versioned_at = $4,
    updated_at = now()
WHERE recipe_id = $1
"""

_UPDATE_DEPRECATED_SQL = """
UPDATE proj_recipe_recipe_summary
SET status = 'Deprecated',
    replaced_by_recipe_id = $2,
    deprecated_at = $3,
    updated_at = now()
WHERE recipe_id = $1
"""


def _steps_count(payload: dict[str, object]) -> int:
    """Count the entries in the payload's wire-format `{steps: {steps: [...]}}`.

    The `body.to_dict` wrapper nests the step list one level deep so the
    JSON shape stays explicit. Defensive: returns 0 if the shape is
    malformed (projection never raises on a single bad event).
    """
    outer = payload.get("steps")
    if not isinstance(outer, dict):
        return 0
    inner = outer.get("steps")
    if not isinstance(inner, list):
        return 0
    return len(inner)


class RecipeSummaryProjection:
    """Maintains the `proj_recipe_recipe_summary` read model."""

    name = "proj_recipe_recipe_summary"
    subscribed_event_types = frozenset(
        {
            "RecipeDefined",
            "RecipeVersioned",
            "RecipeDeprecated",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "RecipeDefined":
                await conn.execute(
                    _INSERT_RECIPE_SQL,
                    UUID(event.payload["recipe_id"]),
                    event.payload["name"],
                    UUID(event.payload["capability_id"]),
                    _steps_count(event.payload),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "RecipeVersioned":
                await conn.execute(
                    _UPDATE_VERSIONED_SQL,
                    UUID(event.payload["recipe_id"]),
                    event.payload["version_tag"],
                    _steps_count(event.payload),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "RecipeDeprecated":
                raw_replaced = event.payload.get("replaced_by_recipe_id")
                replaced = UUID(raw_replaced) if raw_replaced is not None else None
                await conn.execute(
                    _UPDATE_DEPRECATED_SQL,
                    UUID(event.payload["recipe_id"]),
                    replaced,
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case _:
                # Not in our subscription set; defensive no-op.
                return


__all__ = ["RecipeSummaryProjection"]
