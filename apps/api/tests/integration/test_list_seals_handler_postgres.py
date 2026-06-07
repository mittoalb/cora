"""End-to-end integration test: list_seals + projection round-trip.

Seeds 3 Seal singletons (one per unique facility_id suffix) via
`initialize_seal`, transitions one of them into `Republishing` via
`start_seal_republishing`, drains the SealSummaryProjection, then queries
`list_seals` and verifies:

  - all 3 surface in the projection
  - status='Live' filter narrows to the two unaltered seeds
  - status='Republishing' filter narrows to the transitioned seed
  - cursor pagination produces disjoint pages whose union covers the
    seeded set (status='Live' scopes tightly to this test's rows)

Each test mints unique facility_id suffixes so the
`proj_federation_seal_summary` singleton PK on `facility_id` does not collide
across runs sharing the same db_pool. The list-query factory enforces
its cursor over a UUID id; the slice derives that UUID from the row's
facility_id via `seal_stream_id`, so cursor pagination is exercised
against the real UUID5 derivation.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.federation._projections import register_federation_projections
from cora.federation.aggregates.credential import CredentialPurpose, CredentialStatus
from cora.federation.features import (
    initialize_seal,
    list_seals,
    start_seal_republishing,
)
from cora.federation.features.initialize_seal import InitializeSeal
from cora.federation.features.list_seals import ListSeals
from cora.federation.features.start_seal_republishing import StartSealRepublishing
from cora.infrastructure.adapters.in_memory_credential_lookup import (
    InMemoryCredentialLookup,
)
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000fed5e01")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000fed5e02")


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_federation_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


def _facility(tag: str) -> str:
    """Unique facility_id per test seed: collision-free across runs."""
    return f"aps-{tag}-{uuid4().hex[:8]}"


def _register_seal_credentials(
    lookup: InMemoryCredentialLookup,
    *,
    facility_id: str,
    online_credential_id: UUID,
    offline_credential_id: UUID,
) -> None:
    lookup.register(
        credential_id=online_credential_id,
        facility_id=facility_id,
        purpose=CredentialPurpose.SEAL_ONLINE_SIGNING.value,
        status=CredentialStatus.ACTIVE.value,
    )
    lookup.register(
        credential_id=offline_credential_id,
        facility_id=facility_id,
        purpose=CredentialPurpose.SEAL_OFFLINE_ROOT.value,
        status=CredentialStatus.ACTIVE.value,
    )


@pytest.mark.integration
async def test_list_seals_status_filter_postgres(db_pool: asyncpg.Pool) -> None:
    lookup = InMemoryCredentialLookup()
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[uuid4() for _ in range(40)],
        credential_lookup=lookup,
    )

    # Seed 3 Seals on distinct facilities:
    #   s1: status=Live
    #   s2: status=Live -> Republishing (transition)
    #   s3: status=Live
    f1 = _facility("s1")
    f2 = _facility("s2")
    f3 = _facility("s3")

    # Each Seal needs distinct online/offline key refs (key-separation).
    for fid in (f1, f2, f3):
        online_credential_id = uuid4()
        offline_credential_id = uuid4()
        _register_seal_credentials(
            lookup,
            facility_id=fid,
            online_credential_id=online_credential_id,
            offline_credential_id=offline_credential_id,
        )
        await initialize_seal.bind(deps)(
            InitializeSeal(
                facility_id=fid,
                online_credential_id=online_credential_id,
                offline_credential_id=offline_credential_id,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Transition s2 to Republishing
    await start_seal_republishing.bind(deps)(
        StartSealRepublishing(facility_id=f2, reason="integration-test"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)

    handler = list_seals.bind(deps)

    # Unfiltered list MUST contain all 3 seeds (other tests may add more)
    page = await handler(
        ListSeals(limit=100),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    facility_ids = {item.facility_id for item in page.items}
    assert {f1, f2, f3}.issubset(facility_ids)

    # status='Republishing' includes f2 but NOT f1/f3
    page = await handler(
        ListSeals(status="Republishing", limit=100),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    republishing_ids = {item.facility_id for item in page.items}
    assert f2 in republishing_ids
    assert f1 not in republishing_ids
    assert f3 not in republishing_ids
    for item in page.items:
        assert item.status == "Republishing"

    # status='Live' includes f1 and f3 but NOT f2
    page = await handler(
        ListSeals(status="Live", limit=100),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    live_ids = {item.facility_id for item in page.items}
    assert f1 in live_ids
    assert f3 in live_ids
    assert f2 not in live_ids
    for item in page.items:
        assert item.status == "Live"


@pytest.mark.integration
async def test_list_seals_projection_row_shape_postgres(db_pool: asyncpg.Pool) -> None:
    """Single Seal landed via initialize_seal surfaces every column
    on the SealSummaryItem with the expected genesis defaults."""
    lookup = InMemoryCredentialLookup()
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[uuid4() for _ in range(5)],
        credential_lookup=lookup,
    )

    fid = _facility("shape")
    online_credential_id = uuid4()
    offline_credential_id = uuid4()
    _register_seal_credentials(
        lookup,
        facility_id=fid,
        online_credential_id=online_credential_id,
        offline_credential_id=offline_credential_id,
    )
    await initialize_seal.bind(deps)(
        InitializeSeal(
            facility_id=fid,
            online_credential_id=online_credential_id,
            offline_credential_id=offline_credential_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    page = await list_seals.bind(deps)(
        ListSeals(limit=100),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    matched = [item for item in page.items if item.facility_id == fid]
    assert len(matched) == 1
    item = matched[0]
    assert item.online_credential_id == online_credential_id
    assert item.offline_credential_id == offline_credential_id
    assert item.current_head_hash is None
    assert item.current_sequence_number == 0
    assert item.initialized_by == _PRINCIPAL_ID
    assert item.last_signed_by is None
    assert item.status == "Live"
    assert item.initialized_at == _NOW
    assert item.last_signed_at is None


@pytest.mark.integration
async def test_list_seals_cursor_pagination_postgres(db_pool: asyncpg.Pool) -> None:
    """Pagination invariants: page size, non-null cursor mid-page,
    disjoint pages, union covers all 3 seeds.

    The cursor encodes a UUID derived from facility_id via
    `seal_stream_id`; this test exercises that UUID5 round-trip
    through the list_query factory's base64 cursor encoder. The
    transition to Republishing on every seed (via
    `start_seal_republishing` between seeds) lets the status filter
    scope tightly to this test's rows.
    """
    lookup = InMemoryCredentialLookup()
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[uuid4() for _ in range(20)],
        credential_lookup=lookup,
    )

    seeded: list[str] = []
    for i in range(3):
        fid = _facility(f"pag{i}")
        online_credential_id = uuid4()
        offline_credential_id = uuid4()
        _register_seal_credentials(
            lookup,
            facility_id=fid,
            online_credential_id=online_credential_id,
            offline_credential_id=offline_credential_id,
        )
        await initialize_seal.bind(deps)(
            InitializeSeal(
                facility_id=fid,
                online_credential_id=online_credential_id,
                offline_credential_id=offline_credential_id,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        # Transition each into Republishing so the status filter
        # scopes tightly to this test's rows.
        await start_seal_republishing.bind(deps)(
            StartSealRepublishing(facility_id=fid, reason=f"pag{i}"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        seeded.append(fid)

    await _drain(db_pool)

    handler = list_seals.bind(deps)

    # Page 1: limit=2, scoped to Republishing
    page1 = await handler(
        ListSeals(limit=2, status="Republishing"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Other tests in this module may have added Republishing rows;
    # we cannot assume len(page1.items) == 2 strictly, but the cursor
    # should be non-null whenever the projection has more matching
    # rows than the page size. With our 3 seeds (plus any sibling
    # additions), a limit=2 page must always be full + carry a cursor.
    assert len(page1.items) == 2
    assert page1.next_cursor is not None
    page1_ids = {item.facility_id for item in page1.items}

    # Page 2: continue with cursor
    page2 = await handler(
        ListSeals(cursor=page1.next_cursor, limit=2, status="Republishing"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    page2_ids = {item.facility_id for item in page2.items}

    # Disjoint pages, and the union covers every seed we registered
    # in this test (other tests' rows MAY surface in between but
    # cannot duplicate ours, and ours cannot appear in both pages).
    assert page1_ids.isdisjoint(page2_ids)
    # Walk the cursor chain to gather every Republishing row, then
    # confirm our 3 seeded facility_ids are present.
    collected: set[str] = set(page1_ids) | set(page2_ids)
    cursor = page2.next_cursor
    while cursor is not None:
        page = await handler(
            ListSeals(cursor=cursor, limit=2, status="Republishing"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        collected.update(item.facility_id for item in page.items)
        cursor = page.next_cursor
    assert set(seeded).issubset(collected)
