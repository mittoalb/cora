"""End-to-end: `list_supplies` handler against real Postgres projection table.

Pins the genesis -> transition fold + projection writes:

  - SupplyRegistered -> INSERT (status='Unknown', last_status_*=NULL)
  - SupplyMarkedAvailable -> UPDATE status='Available' + last_status_changed_at
                                     + last_status_reason + last_trigger
  - scope filter
  - kind filter
  - status filter
  - cursor pagination
  - 5-status SupplyStatusFilter Literal locked day one (Unknown / Available
    reachable in 10a-a; Degraded / Unavailable / Recovering reachable in 10a-b)
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.supply._projections import register_supply_projections
from cora.supply.aggregates.supply import SupplyScope
from cora.supply.features.list_supplies import ListSupplies
from cora.supply.features.list_supplies import bind as bind_list
from cora.supply.features.mark_supply_available import MarkSupplyAvailable
from cora.supply.features.mark_supply_available import bind as bind_mark
from cora.supply.features.register_supply import RegisterSupply
from cora.supply.features.register_supply import bind as bind_register
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 14, 13, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID], now: datetime = _NOW) -> Kernel:
    return build_postgres_deps(db_pool, now=now, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_supply_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_register_inserts_unknown_status_with_null_audit_columns(
    db_pool: asyncpg.Pool,
) -> None:
    """SupplyRegistered -> projection row in 'Unknown' with last_status_* NULL."""
    sup_id = uuid4()
    deps = _build_deps(db_pool, [sup_id, uuid4()])
    await bind_register(deps)(
        RegisterSupply(scope=SupplyScope.BEAMLINE, kind="LiquidNitrogen", name="35-BM LN2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT scope, kind, name, status, last_status_changed_at, "
            "last_status_reason, last_trigger "
            "FROM proj_supply_summary WHERE supply_id = $1",
            sup_id,
        )
    assert row is not None
    assert row["scope"] == "Beamline"
    assert row["kind"] == "LiquidNitrogen"
    assert row["name"] == "35-BM LN2"
    assert row["status"] == "Unknown"
    assert row["last_status_changed_at"] is None
    assert row["last_status_reason"] is None
    assert row["last_trigger"] is None


@pytest.mark.integration
async def test_mark_available_updates_status_and_audit_triple(
    db_pool: asyncpg.Pool,
) -> None:
    """Register -> mark_available: status flips Available + audit triple lands."""
    sup_id = uuid4()
    deps = _build_deps(db_pool, [sup_id, uuid4()])
    await bind_register(deps)(
        RegisterSupply(scope=SupplyScope.BEAMLINE, kind="LiquidNitrogen", name="35-BM LN2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    later_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_mark(later_deps)(
        MarkSupplyAvailable(supply_id=sup_id, reason="operator walkdown"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, last_status_changed_at, last_status_reason, last_trigger "
            "FROM proj_supply_summary WHERE supply_id = $1",
            sup_id,
        )
    assert row is not None
    assert row["status"] == "Available"
    assert row["last_status_changed_at"] == _LATER
    assert row["last_status_reason"] == "operator walkdown"
    assert row["last_trigger"] == "Operator"


@pytest.mark.integration
async def test_list_returns_registered_supplies(db_pool: asyncpg.Pool) -> None:
    deps = _build_deps(db_pool, [uuid4(), uuid4()])
    await bind_register(deps)(
        RegisterSupply(scope=SupplyScope.BEAMLINE, kind="LiquidNitrogen", name="35-BM LN2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    page = await bind_list(deps)(
        ListSupplies(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].name == "35-BM LN2"
    assert page.items[0].status == "Unknown"
    assert page.next_cursor is None


@pytest.mark.integration
async def test_list_filters_by_scope_kind_status(db_pool: asyncpg.Pool) -> None:
    """All three filters work in combination via the NULL-or pattern."""
    # Register 3 supplies across different scope/kind/status combinations.
    bm_ln2_id = uuid4()
    fac_beam_id = uuid4()
    bm_air_id = uuid4()

    for sup_id, scope, kind, name in (
        (bm_ln2_id, SupplyScope.BEAMLINE, "LiquidNitrogen", "35-BM LN2"),
        (fac_beam_id, SupplyScope.FACILITY, "PhotonBeam", "APS storage-ring beam"),
        (bm_air_id, SupplyScope.BEAMLINE, "CompressedAir", "35-BM CompAir"),
    ):
        deps = _build_deps(db_pool, [sup_id, uuid4()])
        await bind_register(deps)(
            RegisterSupply(scope=scope, kind=kind, name=name),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    # Mark only the LN2 one Available
    mark_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_mark(mark_deps)(
        MarkSupplyAvailable(supply_id=bm_ln2_id, reason="operator walkdown"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])

    # Filter by scope=Beamline -> 2 results
    page = await bind_list(list_deps)(
        ListSupplies(scope="Beamline"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 2
    assert {item.kind for item in page.items} == {"LiquidNitrogen", "CompressedAir"}

    # Filter by kind=PhotonBeam -> 1 result
    page = await bind_list(list_deps)(
        ListSupplies(kind="PhotonBeam"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].name == "APS storage-ring beam"

    # Filter by status=Available -> 1 result (only the marked one)
    page = await bind_list(list_deps)(
        ListSupplies(status="Available"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].supply_id == bm_ln2_id

    # Combined: scope=Beamline AND status=Unknown -> 1 result (CompAir)
    page = await bind_list(list_deps)(
        ListSupplies(scope="Beamline", status="Unknown"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].supply_id == bm_air_id


@pytest.mark.integration
async def test_list_cursor_pagination(db_pool: asyncpg.Pool) -> None:
    """Pages-of-2 across 3 supplies produces a cursor on page 1, no cursor on page 2."""
    for i in range(3):
        deps = _build_deps(db_pool, [uuid4(), uuid4()])
        await bind_register(deps)(
            RegisterSupply(scope=SupplyScope.BEAMLINE, kind=f"K{i}", name=f"Supply-{i}"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])
    page1 = await bind_list(list_deps)(
        ListSupplies(limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page1.items) == 2
    assert page1.next_cursor is not None

    page2 = await bind_list(list_deps)(
        ListSupplies(limit=2, cursor=page1.next_cursor),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page2.items) == 1
    assert page2.next_cursor is None


@pytest.mark.integration
async def test_list_returns_audit_triple_after_mark_available(
    db_pool: asyncpg.Pool,
) -> None:
    """H1 from gate review: pin the round-trip of `last_status_changed_at` /
    `last_status_reason` / `last_trigger` from projection -> handler item ->
    list response. Without this, a regression breaking the field-mapping
    SQL or the SupplySummaryItem construction would ship green."""
    sup_id = uuid4()
    register_deps = _build_deps(db_pool, [sup_id, uuid4()])
    await bind_register(register_deps)(
        RegisterSupply(scope=SupplyScope.BEAMLINE, kind="LiquidNitrogen", name="35-BM LN2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    mark_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_mark(mark_deps)(
        MarkSupplyAvailable(supply_id=sup_id, reason="operator walkdown confirms LN2 flowing"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])
    page = await bind_list(list_deps)(
        ListSupplies(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    item = page.items[0]
    assert item.status == "Available"
    assert item.last_status_changed_at == _LATER
    assert item.last_status_reason == "operator walkdown confirms LN2 flowing"
    assert item.last_trigger == "Operator"


@pytest.mark.integration
async def test_list_cursor_with_filter_paginates_within_filtered_set(
    db_pool: asyncpg.Pool,
) -> None:
    """M3 from gate review: cursor + filter in combination exercises the
    `_LIST_WITH_CURSOR_SQL` branch (the more complex SQL path) under
    real filter pressure. Register 3 Beamline + 1 Facility, page-of-2
    with scope=Beamline, expect page1 to have a cursor, page2 to have
    the remaining Beamline supply only."""
    for i in range(3):
        deps = _build_deps(db_pool, [uuid4(), uuid4()])
        await bind_register(deps)(
            RegisterSupply(scope=SupplyScope.BEAMLINE, kind=f"K{i}", name=f"BM-{i}"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    facility_deps = _build_deps(db_pool, [uuid4(), uuid4()])
    await bind_register(facility_deps)(
        RegisterSupply(scope=SupplyScope.FACILITY, kind="PhotonBeam", name="APS-Beam"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])
    page1 = await bind_list(list_deps)(
        ListSupplies(scope="Beamline", limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page1.items) == 2
    assert all(item.scope == "Beamline" for item in page1.items)
    assert page1.next_cursor is not None

    page2 = await bind_list(list_deps)(
        ListSupplies(scope="Beamline", limit=2, cursor=page1.next_cursor),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page2.items) == 1
    assert page2.items[0].scope == "Beamline"
    assert page2.next_cursor is None


@pytest.mark.integration
async def test_list_unique_address_swallows_second_insert_and_keeps_worker_running(
    db_pool: asyncpg.Pool,
) -> None:
    """Duplicate-key UniqueViolation in the projection is caught and logged.

    Two supplies with the same (scope, kind, name) trip the projection's
    UNIQUE INDEX on the second INSERT. The projection catches the
    UniqueViolation, logs a structured warning, and advances the bookmark
    so the worker keeps running. Operational behavior verified:

      - Both Supply event streams exist in the event store (the duplicate
        registration is audit-recorded, not silently dropped at the
        write layer).
      - The projection has exactly one row (the first insert wins; the
        second's INSERT is a no-op via the catch).
      - The drain itself does NOT raise (worker would otherwise stall
        and block all Supply projection progress including transitions
        on unrelated supplies).

    The aggregate cannot enforce cross-stream uniqueness without DCB
    (see [[project_deferred]]); graceful projection-level handling is
    the right operational behavior pre-DCB. Operators discover the
    duplicate via list_supplies and reconcile via the future
    `deregister_supply` slice (Watch item 10).
    """
    sup_id_1 = uuid4()
    sup_id_2 = uuid4()
    for sup_id in (sup_id_1, sup_id_2):
        deps = _build_deps(db_pool, [sup_id, uuid4()])
        await bind_register(deps)(
            RegisterSupply(
                scope=SupplyScope.BEAMLINE,
                kind="LiquidNitrogen",
                name="35-BM LN2",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    # Drain succeeds (UniqueViolation caught + logged + swallowed).
    await _drain(db_pool)

    # Exactly one projection row (first insert wins).
    list_deps = _build_deps(db_pool, [])
    page = await bind_list(list_deps)(
        ListSupplies(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].supply_id in {sup_id_1, sup_id_2}

    # Both Supply event streams exist in the event store (audit preserved).
    async with db_pool.acquire() as conn:
        row_count = await conn.fetchval("SELECT count(*) FROM events WHERE stream_type = 'Supply'")
    assert row_count == 2
