"""Integration tests for the early-return branch in each Trust
summary projection.

Each Trust projection (`Conduit`/`Policy`/`Zone`SummaryProjection)
guards its `apply()` body with `if event.event_type != <expected>:
return`. The dispatcher would never feed an unsubscribed event in
practice, but the guard is a defensive belt-and-braces check. These
tests pin the branch by calling `apply()` directly with a wrong-type
StoredEvent and asserting (a) no exception, (b) the projection table
stays empty.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.trust.projections import (
    ConduitSummaryProjection,
    PolicySummaryProjection,
    ZoneSummaryProjection,
)

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Trust",
        stream_id=uuid4(),
        version=1,
        event_type=event_type,
        schema_version=1,
        payload={},
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("projection", "wrong_event_type", "table"),
    [
        (
            ConduitSummaryProjection(),
            "ZoneDefined",
            "proj_trust_conduit_summary",
        ),
        (
            PolicySummaryProjection(),
            "ConduitDefined",
            "proj_trust_policy_summary",
        ),
        (
            ZoneSummaryProjection(),
            "ConduitDefined",
            "proj_trust_zone_summary",
        ),
    ],
)
async def test_projection_apply_is_noop_for_unsubscribed_event(
    db_pool: asyncpg.Pool,
    projection: object,
    wrong_event_type: str,
    table: str,
) -> None:
    event = _stored(wrong_event_type)
    async with db_pool.acquire() as conn:
        await projection.apply(event, conn)  # type: ignore[attr-defined]
        count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
    assert count == 0
