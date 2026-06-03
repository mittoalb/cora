"""FixtureSummaryProjection: folds the Fixture aggregate's single
genesis event into the `proj_equipment_fixture_summary` read model.

Subscribed events (v1):
  - FixtureRegistered -> INSERT (snapshot of assembly_content_hash,
                          surface_id, plus binding_count and
                          override_count for cheap summary reads).

Single-event genesis: idempotent via ON CONFLICT DO NOTHING. The
full slot_asset_bindings stays in the event payload; this read
model is summary-only by design.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from typing import cast
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_FIXTURE_SQL = """
INSERT INTO proj_equipment_fixture_summary
    (fixture_id, assembly_id, assembly_content_hash, surface_id,
     binding_count, override_count, created_at)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (fixture_id) DO NOTHING
"""


class FixtureSummaryProjection:
    """Maintains the `proj_equipment_fixture_summary` read model."""

    name = "proj_equipment_fixture_summary"
    subscribed_event_types = frozenset({"FixtureRegistered"})

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "FixtureRegistered":
                payload = event.payload
                bindings = cast("list[dict[str, object]]", payload["slot_asset_bindings"])
                overrides = cast("dict[str, object]", payload["parameter_overrides"])
                await conn.execute(
                    _INSERT_FIXTURE_SQL,
                    UUID(str(payload["fixture_id"])),
                    UUID(str(payload["assembly_id"])),
                    payload["assembly_content_hash"],
                    UUID(str(payload["surface_id"])),
                    len(bindings),
                    len(overrides),
                    datetime.fromisoformat(str(payload["occurred_at"])),
                )
            case _:
                pass


__all__ = ["FixtureSummaryProjection"]
