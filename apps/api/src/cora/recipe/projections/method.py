"""MethodSummaryProjection: folds the Method aggregate's
4 events into the `proj_recipe_method_summary`
read model that backs `GET /methods`.

Subscribed events:
  - MethodDefined                  -> INSERT (status=Defined,
                                              version_tag=NULL,
                                              parameters_schema_present=FALSE)
  - MethodVersioned                -> UPDATE status=Versioned + version_tag
                                              from payload
  - MethodDeprecated               -> UPDATE status=Deprecated (version_tag
                                              preserved on purpose; the
                                              audit trail of "last revised
                                              at version X before
                                              deprecation" stays visible)
  - MethodParametersSchemaUpdated  -> UPDATE parameters_schema_present
                                              (TRUE if parameters_schema is
                                              non-NULL; FALSE if cleared
                                              via NULL) (Phase 6g-a)

All branches idempotent. `version_tag` lands in the projection ONLY
on MethodVersioned; the Defined INSERT leaves it NULL and the
Deprecated UPDATE doesn't touch it. `parameters_schema_present` is
TRUE iff the latest `MethodParametersSchemaUpdated.parameters_schema`
payload was non-NULL; the schema content itself lives in the event
stream (loaded on demand, not projected to keep the summary table
small). Mirrors `FamilySummaryProjection` (Equipment 5g-a).

`needed_families` from the genesis payload is intentionally NOT
in this projection: it's a list, the keyset+filter shape doesn't
need it, and a future `proj_recipe_method_capabilities` join
projection can carry it when use cases demand "all methods needing
Family X".
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_METHOD_SQL = """
INSERT INTO proj_recipe_method_summary
    (method_id, name, status, version_tag, created_at,
     parameters_schema_present)
VALUES ($1, $2, 'Defined', NULL, $3, FALSE)
ON CONFLICT (method_id) DO NOTHING
"""

_UPDATE_VERSIONED_SQL = """
UPDATE proj_recipe_method_summary
SET status = 'Versioned', version_tag = $2, updated_at = now()
WHERE method_id = $1
"""

_UPDATE_DEPRECATED_SQL = """
UPDATE proj_recipe_method_summary
SET status = 'Deprecated', updated_at = now()
WHERE method_id = $1
"""

_UPDATE_PARAMETERS_SCHEMA_PRESENT_SQL = """
UPDATE proj_recipe_method_summary
SET parameters_schema_present = $2, updated_at = now()
WHERE method_id = $1
"""


class MethodSummaryProjection:
    """Maintains the `proj_recipe_method_summary` read model."""

    name = "proj_recipe_method_summary"
    subscribed_event_types = frozenset(
        {
            "MethodDefined",
            "MethodVersioned",
            "MethodDeprecated",
            "MethodParametersSchemaUpdated",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "MethodDefined":
                await conn.execute(
                    _INSERT_METHOD_SQL,
                    UUID(event.payload["method_id"]),
                    event.payload["name"],
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "MethodVersioned":
                await conn.execute(
                    _UPDATE_VERSIONED_SQL,
                    UUID(event.payload["method_id"]),
                    event.payload["version_tag"],
                )
            case "MethodDeprecated":
                await conn.execute(
                    _UPDATE_DEPRECATED_SQL,
                    UUID(event.payload["method_id"]),
                )
            case "MethodParametersSchemaUpdated":
                await conn.execute(
                    _UPDATE_PARAMETERS_SCHEMA_PRESENT_SQL,
                    UUID(event.payload["method_id"]),
                    event.payload.get("parameters_schema") is not None,
                )
            case _:
                pass


__all__ = ["MethodSummaryProjection"]
