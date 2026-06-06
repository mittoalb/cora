"""End-to-end: decommission_frame slice's projection precondition
(frame_consumers) against real Postgres.

The frame_consumers projection is polymorphic: it tracks two consumer
types of any given Frame:

  - child Frames (whose parent_id points at this frame)
  - active Mounts (whose placement.parent_frame_id points at this frame)

The decommission_frame handler loads load_active_frame_consumers()
and the decider raises FrameInUseError if the tuple is non-empty.
This test pins the polymorphic INSERT + the typed DELETE + the
handler-level reject end-to-end.

Pins:
  - FrameRegistered with non-None parent_id -> INSERT
    (referenced=parent, consumer=child, type='Frame')
  - FrameRegistered with parent_id=None (root) -> no INSERT
  - MountRegistered -> INSERT (referenced=placement.parent_frame_id,
    consumer=mount_id, type='Mount')
  - FrameDecommissioned -> DELETE the type='Frame' row only
  - MountDecommissioned -> DELETE the type='Mount' row only
  - decommission_frame rejected when active Mount consumer exists
  - decommission_frame rejected when active child Frame consumer exists
  - decommission_frame succeeds once both consumer types are gone
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.frame import FrameInUseError
from cora.equipment.features.decommission_frame import DecommissionFrame
from cora.equipment.features.decommission_frame import bind as bind_decommission_frame
from cora.equipment.features.decommission_mount import DecommissionMount
from cora.equipment.features.decommission_mount import bind as bind_decommission_mount
from cora.equipment.features.register_frame import RegisterFrame
from cora.equipment.features.register_frame import bind as bind_register_frame
from cora.equipment.features.register_mount import RegisterMount
from cora.equipment.features.register_mount import bind as bind_register_mount
from cora.equipment.projections.frame_consumers import load_active_frame_consumers
from cora.infrastructure.kernel import Kernel
from tests.integration._equipment_helpers import drain_equipment_projections, placement
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 31, 11, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 31, 12, 30, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(pool: asyncpg.Pool, ids: list[UUID], now: datetime = _NOW) -> Kernel:
    return build_postgres_deps(pool, now=now, ids=ids)


async def _seed_root_frame(pool: asyncpg.Pool, frame_id: UUID) -> None:
    deps = _build_deps(pool, [frame_id, uuid4()])
    await bind_register_frame(deps)(
        RegisterFrame(
            name=f"root-{frame_id}",
            parent_id=None,
            placement=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_child_frame(
    pool: asyncpg.Pool,
    *,
    frame_id: UUID,
    parent_id: UUID,
) -> None:
    deps = _build_deps(pool, [frame_id, uuid4()])
    await bind_register_frame(deps)(
        RegisterFrame(
            name=f"child-{frame_id}",
            parent_id=parent_id,
            placement=placement(parent_id),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_mount(
    pool: asyncpg.Pool,
    *,
    mount_id: UUID,
    parent_frame_id: UUID,
    slot_code: str,
) -> None:
    deps = _build_deps(pool, [mount_id, uuid4()])
    await bind_register_mount(deps)(
        RegisterMount(
            slot_code=slot_code,
            parent_id=None,
            placement=placement(parent_frame_id),
            drawing=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_root_frame_inserts_no_consumer_row(db_pool: asyncpg.Pool) -> None:
    """A root Frame (parent_id=None) is no other Frame's consumer
    and should not appear in the projection until something references
    it."""
    root_id = uuid4()
    await _seed_root_frame(db_pool, root_id)
    await drain_equipment_projections(db_pool)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT consumer_id FROM proj_equipment_frame_consumers WHERE consumer_id = $1",
            root_id,
        )
    assert rows == []


@pytest.mark.integration
async def test_child_frame_inserts_frame_typed_consumer_row(
    db_pool: asyncpg.Pool,
) -> None:
    parent_id, child_id = uuid4(), uuid4()
    await _seed_root_frame(db_pool, parent_id)
    await _seed_child_frame(db_pool, frame_id=child_id, parent_id=parent_id)
    await drain_equipment_projections(db_pool)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT consumer_id, consumer_type FROM proj_equipment_frame_consumers "
            "WHERE referenced_frame_id = $1",
            parent_id,
        )
    assert len(rows) == 1
    assert rows[0]["consumer_id"] == child_id
    assert rows[0]["consumer_type"] == "Frame"

    consumers = await load_active_frame_consumers(db_pool, parent_id)
    assert consumers == (child_id,)


@pytest.mark.integration
async def test_mount_inserts_mount_typed_consumer_row(db_pool: asyncpg.Pool) -> None:
    frame_id, mount_id = uuid4(), uuid4()
    await _seed_root_frame(db_pool, frame_id)
    await _seed_mount(
        db_pool,
        mount_id=mount_id,
        parent_frame_id=frame_id,
        slot_code="02-BM-A-K-consumer",
    )
    await drain_equipment_projections(db_pool)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT consumer_id, consumer_type FROM proj_equipment_frame_consumers "
            "WHERE referenced_frame_id = $1",
            frame_id,
        )
    assert len(rows) == 1
    assert rows[0]["consumer_id"] == mount_id
    assert rows[0]["consumer_type"] == "Mount"


@pytest.mark.integration
async def test_decommission_frame_rejected_while_child_frame_active(
    db_pool: asyncpg.Pool,
) -> None:
    """Load-bearing fitness for the Frame-type consumer leg."""
    parent_id, child_id = uuid4(), uuid4()
    await _seed_root_frame(db_pool, parent_id)
    await _seed_child_frame(db_pool, frame_id=child_id, parent_id=parent_id)
    await drain_equipment_projections(db_pool)

    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    with pytest.raises(FrameInUseError) as info:
        await bind_decommission_frame(deps)(
            DecommissionFrame(frame_id=parent_id, reason="early teardown"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert info.value.frame_id == parent_id
    assert child_id in info.value.consumer_ids


@pytest.mark.integration
async def test_decommission_frame_rejected_while_mount_consumer_active(
    db_pool: asyncpg.Pool,
) -> None:
    """Load-bearing fitness for the Mount-type consumer leg: a Mount's
    placement.parent_frame_id keeps the Frame alive even when no child
    Frame references it."""
    frame_id, mount_id = uuid4(), uuid4()
    await _seed_root_frame(db_pool, frame_id)
    await _seed_mount(
        db_pool,
        mount_id=mount_id,
        parent_frame_id=frame_id,
        slot_code="02-BM-B-K-frame-consumer",
    )
    await drain_equipment_projections(db_pool)

    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    with pytest.raises(FrameInUseError) as info:
        await bind_decommission_frame(deps)(
            DecommissionFrame(frame_id=frame_id, reason="reorg"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert info.value.frame_id == frame_id
    assert mount_id in info.value.consumer_ids


@pytest.mark.integration
async def test_decommission_mount_clears_mount_typed_row_only(
    db_pool: asyncpg.Pool,
) -> None:
    """The typed DELETE filters by (consumer_id, consumer_type): a
    decommissioned Mount must not accidentally remove a Frame-typed
    row that happens to share its UUID (impossible under UUIDv7 but
    pinned defensively)."""
    frame_id, mount_id = uuid4(), uuid4()
    await _seed_root_frame(db_pool, frame_id)
    await _seed_mount(
        db_pool,
        mount_id=mount_id,
        parent_frame_id=frame_id,
        slot_code="02-BM-C-K-typed-delete",
    )
    await drain_equipment_projections(db_pool)
    assert mount_id in await load_active_frame_consumers(db_pool, frame_id)

    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_decommission_mount(deps)(
        DecommissionMount(mount_id=mount_id, reason="moved"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    assert await load_active_frame_consumers(db_pool, frame_id) == ()


@pytest.mark.integration
async def test_decommission_frame_succeeds_once_all_consumers_gone(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy teardown: with no active consumers, decommission_frame
    emits FrameDecommissioned successfully. Closes the loop on the
    two rejection tests above."""
    frame_id, mount_id = uuid4(), uuid4()
    await _seed_root_frame(db_pool, frame_id)
    await _seed_mount(
        db_pool,
        mount_id=mount_id,
        parent_frame_id=frame_id,
        slot_code="02-BM-D-K-clear",
    )
    await drain_equipment_projections(db_pool)

    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_decommission_mount(deps)(
        DecommissionMount(mount_id=mount_id, reason="moved"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)
    assert await load_active_frame_consumers(db_pool, frame_id) == ()

    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_decommission_frame(deps)(
        DecommissionFrame(frame_id=frame_id, reason="reorg"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
