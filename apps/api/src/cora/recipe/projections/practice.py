"""PracticeSummaryProjection: folds the Practice aggregate's 3
lifecycle events into the `proj_recipe_practice_summary` read model
that backs `GET /practices` and supplies lifecycle timestamps to
`GET /practices/{id}` (Path C).

Subscribed events:
  - PracticeDefined    -> INSERT (status=Defined, version_tag=NULL,
                                  created_at=payload.occurred_at,
                                  method_id + site_id from payload)
  - PracticeVersioned  -> UPDATE status=Versioned + version_tag from payload
                                  + versioned_at=payload.occurred_at
                                  (overwritten on each re-version)
  - PracticeDeprecated -> UPDATE status=Deprecated +
                                  deprecated_at=payload.occurred_at
                                  (version_tag preserved)

`method_id` and `site_id` come from the genesis event and never
change (no event re-issues them), so the INSERT carries them and
later updates leave them alone. method_id surfaces the cross-
aggregate filter ("show me all Practices implementing Method X").

`versioned_at` / `deprecated_at` source: Path C lock — state stays
decider-minimal, projections carry lifecycle metadata. Mirrors
MethodSummaryProjection and PlanSummaryProjection.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_PRACTICE_SQL = """
INSERT INTO proj_recipe_practice_summary
    (practice_id, name, method_id, site_id, status, version_tag, created_at)
VALUES ($1, $2, $3, $4, 'Defined', NULL, $5)
ON CONFLICT (practice_id) DO NOTHING
"""

_UPDATE_VERSIONED_SQL = """
UPDATE proj_recipe_practice_summary
SET status = 'Versioned',
    version_tag = $2,
    versioned_at = $3,
    updated_at = now()
WHERE practice_id = $1
"""

_UPDATE_DEPRECATED_SQL = """
UPDATE proj_recipe_practice_summary
SET status = 'Deprecated',
    deprecated_at = $2,
    updated_at = now()
WHERE practice_id = $1
"""


class PracticeSummaryProjection:
    """Maintains the `proj_recipe_practice_summary` read model."""

    name = "proj_recipe_practice_summary"
    subscribed_event_types = frozenset(
        {"PracticeDefined", "PracticeVersioned", "PracticeDeprecated"}
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "PracticeDefined":
                await conn.execute(
                    _INSERT_PRACTICE_SQL,
                    UUID(event.payload["practice_id"]),
                    event.payload["name"],
                    UUID(event.payload["method_id"]),
                    UUID(event.payload["site_id"]),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "PracticeVersioned":
                await conn.execute(
                    _UPDATE_VERSIONED_SQL,
                    UUID(event.payload["practice_id"]),
                    event.payload["version_tag"],
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "PracticeDeprecated":
                await conn.execute(
                    _UPDATE_DEPRECATED_SQL,
                    UUID(event.payload["practice_id"]),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case _:
                pass


__all__ = ["PracticeSummaryProjection"]
