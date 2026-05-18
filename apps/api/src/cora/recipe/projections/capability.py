"""RecipeCapabilitySummaryProjection: folds the Capability aggregate's
lifecycle events into `proj_recipe_capability_summary`.

Distinct from `FamilySummaryProjection` (Equipment BC). Family =
device-class; Capability = operations-layer template per DLM-B.

Subscribed events:
  - CapabilityDefined   -> INSERT (status=Defined, version_tag=NULL,
                                   replaced_by_capability_id=NULL,
                                   declarative fields from payload)
  - CapabilityVersioned -> UPDATE status=Versioned + version_tag +
                                   REFRESH declarative fields
                                   (a new version IS a new declaration)
  - CapabilityDeprecated -> UPDATE status=Deprecated +
                                   replaced_by_capability_id
                                   (declarative fields PRESERVED for audit)

All branches idempotent. `version_tag` lands ONLY on Versioned;
Defined INSERT leaves it NULL and Deprecated UPDATE doesn't touch it.
`parameter_schema_present` is TRUE iff the latest event's
parameter_schema payload was non-NULL; the schema content itself
lives in the event stream (loaded on demand to keep summary small).
`required_affordances` and `executor_shapes` ship as text[] for
future filter consumers (deferred per DLM-B locks).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_CAPABILITY_SQL = """
INSERT INTO proj_recipe_capability_summary
    (capability_id, code, name, status, version_tag, description,
     required_affordances, executor_shapes, parameter_schema_present,
     replaced_by_capability_id, created_at)
VALUES ($1, $2, $3, 'Defined', NULL, $4, $5, $6, $7, NULL, $8)
ON CONFLICT (capability_id) DO NOTHING
"""

_UPDATE_VERSIONED_SQL = """
UPDATE proj_recipe_capability_summary
SET status = 'Versioned',
    version_tag = $2,
    description = $3,
    required_affordances = $4,
    executor_shapes = $5,
    parameter_schema_present = $6,
    updated_at = now()
WHERE capability_id = $1
"""

_UPDATE_DEPRECATED_SQL = """
UPDATE proj_recipe_capability_summary
SET status = 'Deprecated',
    replaced_by_capability_id = $2,
    updated_at = now()
WHERE capability_id = $1
"""


class RecipeCapabilitySummaryProjection:
    """Maintains the `proj_recipe_capability_summary` read model."""

    name = "proj_recipe_capability_summary"
    subscribed_event_types = frozenset(
        {
            "CapabilityDefined",
            "CapabilityVersioned",
            "CapabilityDeprecated",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "CapabilityDefined":
                await conn.execute(
                    _INSERT_CAPABILITY_SQL,
                    UUID(event.payload["capability_id"]),
                    event.payload["code"],
                    event.payload["name"],
                    event.payload.get("description"),
                    event.payload.get("required_affordances", []),
                    event.payload.get("executor_shapes", []),
                    event.payload.get("parameter_schema") is not None,
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "CapabilityVersioned":
                await conn.execute(
                    _UPDATE_VERSIONED_SQL,
                    UUID(event.payload["capability_id"]),
                    event.payload["version_tag"],
                    event.payload.get("description"),
                    event.payload.get("required_affordances", []),
                    event.payload.get("executor_shapes", []),
                    event.payload.get("parameter_schema") is not None,
                )
            case "CapabilityDeprecated":
                replaced_raw = event.payload.get("replaced_by_capability_id")
                await conn.execute(
                    _UPDATE_DEPRECATED_SQL,
                    UUID(event.payload["capability_id"]),
                    UUID(replaced_raw) if replaced_raw is not None else None,
                )
            case _:
                pass


__all__ = ["RecipeCapabilitySummaryProjection"]
