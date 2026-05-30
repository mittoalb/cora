"""End-to-end: register_mount with a non-null parent_mount_id lands
the expected (parent, child) edge in proj_equipment_mount_children
against real Postgres, and a decommissioned child's row is removed.

The mount_children projection backs the decommission_mount slice's
precondition: a parent Mount cannot be decommissioned while any
active child Mount references it (no cascade-decommission per the
design anti-hook). This test is the load-bearing fitness for that
write-side / read-side pairing.

Pins:
  - MountRegistered with parent_mount_id != None -> INSERT (parent, child)
  - MountRegistered with parent_mount_id == None (top-level) -> no INSERT
  - MountDecommissioned (on a child) -> DELETE the (parent, child) row
  - load_active_mount_children query helper returns the live child set
  - decommission_mount handler rejects a parent that still has live
    children via the projection-loaded MountHasActiveChildrenError
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates._placement import (
    Placement,
    ReferenceSurface,
    UnitSystem,
)
from cora.equipment.aggregates.mount import MountHasActiveChildrenError
from cora.equipment.features.decommission_mount import DecommissionMount
from cora.equipment.features.decommission_mount import bind as bind_decommission_mount
from cora.equipment.features.register_frame import RegisterFrame
from cora.equipment.features.register_frame import bind as bind_register_frame
from cora.equipment.features.register_mount import RegisterMount
from cora.equipment.features.register_mount import bind as bind_register_mount
from cora.equipment.projections.mount_children import load_active_mount_children
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 31, 9, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 31, 10, 30, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _placement(parent_frame_id: UUID) -> Placement:
    return Placement(
        x=0.0,
        y=0.0,
        z=0.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame=parent_frame_id,
        reference_surface=ReferenceSurface.SHIELDING_FACE,
        tol_x=0.1,
        tol_y=0.1,
        tol_z=0.1,
        tol_rx=0.0,
        tol_ry=0.0,
        tol_rz=0.0,
        units=UnitSystem.SI_MM_RAD,
    )


def _build_deps(pool: asyncpg.Pool, ids: list[UUID], now: datetime = _NOW) -> Kernel:
    return build_postgres_deps(pool, now=now, ids=ids)


async def _drain(pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(pool, registry, deadline_seconds=2.0)


async def _seed_frame(pool: asyncpg.Pool, frame_id: UUID) -> None:
    deps = _build_deps(pool, [frame_id, uuid4()])
    await bind_register_frame(deps)(
        RegisterFrame(
            name=f"frame-{frame_id}",
            parent_frame_id=None,
            placement_relative_to_parent=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_mount(
    pool: asyncpg.Pool,
    *,
    mount_id: UUID,
    parent_mount_id: UUID | None,
    placement: Placement,
    slot_code: str,
) -> None:
    deps = _build_deps(pool, [mount_id, uuid4()])
    await bind_register_mount(deps)(
        RegisterMount(
            slot_code=slot_code,
            parent_mount_id=parent_mount_id,
            placement=placement,
            drawing=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_top_level_mount_inserts_no_children_row(db_pool: asyncpg.Pool) -> None:
    """A Mount with parent_mount_id=None is a top-level slot; it
    should NOT appear as a child of anything in the projection."""
    frame_id = uuid4()
    await _seed_frame(db_pool, frame_id)
    top_id = uuid4()
    await _seed_mount(
        db_pool,
        mount_id=top_id,
        parent_mount_id=None,
        placement=_placement(frame_id),
        slot_code="02-BM-A-K-top",
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT parent_mount_id, child_mount_id "
            "FROM proj_equipment_mount_children "
            "WHERE child_mount_id = $1",
            top_id,
        )
    assert rows == []


@pytest.mark.integration
async def test_child_mount_inserts_parent_to_child_edge(db_pool: asyncpg.Pool) -> None:
    frame_id = uuid4()
    await _seed_frame(db_pool, frame_id)
    parent_id, child_id = uuid4(), uuid4()
    await _seed_mount(
        db_pool,
        mount_id=parent_id,
        parent_mount_id=None,
        placement=_placement(frame_id),
        slot_code="02-BM-A-K-parent",
    )
    await _seed_mount(
        db_pool,
        mount_id=child_id,
        parent_mount_id=parent_id,
        placement=_placement(frame_id),
        slot_code="02-BM-A-K-child",
    )
    await _drain(db_pool)

    children = await load_active_mount_children(db_pool, parent_id)
    assert children == (child_id,)


@pytest.mark.integration
async def test_decommission_child_deletes_parent_to_child_edge(
    db_pool: asyncpg.Pool,
) -> None:
    frame_id = uuid4()
    await _seed_frame(db_pool, frame_id)
    parent_id, child_id = uuid4(), uuid4()
    await _seed_mount(
        db_pool,
        mount_id=parent_id,
        parent_mount_id=None,
        placement=_placement(frame_id),
        slot_code="02-BM-B-K-parent",
    )
    await _seed_mount(
        db_pool,
        mount_id=child_id,
        parent_mount_id=parent_id,
        placement=_placement(frame_id),
        slot_code="02-BM-B-K-child",
    )
    await _drain(db_pool)
    assert await load_active_mount_children(db_pool, parent_id) == (child_id,)

    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_decommission_mount(deps)(
        DecommissionMount(mount_id=child_id, reason="reconfig"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    assert await load_active_mount_children(db_pool, parent_id) == ()


@pytest.mark.integration
async def test_two_children_decommission_one_leaves_other_edge_intact(
    db_pool: asyncpg.Pool,
) -> None:
    """Pin against a `DELETE WHERE parent_mount_id = $1` substitution
    bug: a parent with two children, decommissioning one child must
    delete exactly that edge and leave the sibling edge intact."""
    frame_id = uuid4()
    await _seed_frame(db_pool, frame_id)
    parent_id, child_keep, child_drop = uuid4(), uuid4(), uuid4()
    await _seed_mount(
        db_pool,
        mount_id=parent_id,
        parent_mount_id=None,
        placement=_placement(frame_id),
        slot_code="02-BM-D-K-parent",
    )
    await _seed_mount(
        db_pool,
        mount_id=child_keep,
        parent_mount_id=parent_id,
        placement=_placement(frame_id),
        slot_code="02-BM-D-K-keep",
    )
    await _seed_mount(
        db_pool,
        mount_id=child_drop,
        parent_mount_id=parent_id,
        placement=_placement(frame_id),
        slot_code="02-BM-D-K-drop",
    )
    await _drain(db_pool)
    assert set(await load_active_mount_children(db_pool, parent_id)) == {
        child_keep,
        child_drop,
    }

    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_decommission_mount(deps)(
        DecommissionMount(mount_id=child_drop, reason="single-child teardown"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    assert await load_active_mount_children(db_pool, parent_id) == (child_keep,)


@pytest.mark.integration
async def test_decommission_child_then_parent_succeeds_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """The happy teardown path: once the last child is decommissioned,
    the parent's mount_children precondition is empty and the parent
    decommissions cleanly. Closes the loop on the precedent set by
    test_decommission_parent_rejected_while_child_active."""
    frame_id = uuid4()
    await _seed_frame(db_pool, frame_id)
    parent_id, child_id = uuid4(), uuid4()
    await _seed_mount(
        db_pool,
        mount_id=parent_id,
        parent_mount_id=None,
        placement=_placement(frame_id),
        slot_code="02-BM-E-K-parent",
    )
    await _seed_mount(
        db_pool,
        mount_id=child_id,
        parent_mount_id=parent_id,
        placement=_placement(frame_id),
        slot_code="02-BM-E-K-child",
    )
    await _drain(db_pool)

    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_decommission_mount(deps)(
        DecommissionMount(mount_id=child_id, reason="child first"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)
    assert await load_active_mount_children(db_pool, parent_id) == ()

    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_decommission_mount(deps)(
        DecommissionMount(mount_id=parent_id, reason="parent after"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_decommission_parent_rejected_while_child_active(
    db_pool: asyncpg.Pool,
) -> None:
    """Load-bearing fitness: the handler reads the mount_children
    projection at decide-time and raises MountHasActiveChildrenError
    when the row set is non-empty. This is the single-stream-write +
    projection-precondition pattern's live test against Postgres."""
    frame_id = uuid4()
    await _seed_frame(db_pool, frame_id)
    parent_id, child_id = uuid4(), uuid4()
    await _seed_mount(
        db_pool,
        mount_id=parent_id,
        parent_mount_id=None,
        placement=_placement(frame_id),
        slot_code="02-BM-C-K-parent",
    )
    await _seed_mount(
        db_pool,
        mount_id=child_id,
        parent_mount_id=parent_id,
        placement=_placement(frame_id),
        slot_code="02-BM-C-K-child",
    )
    await _drain(db_pool)

    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    with pytest.raises(MountHasActiveChildrenError) as info:
        await bind_decommission_mount(deps)(
            DecommissionMount(mount_id=parent_id, reason="early teardown"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert info.value.mount_id == parent_id
    assert child_id in info.value.active_child_mount_ids
