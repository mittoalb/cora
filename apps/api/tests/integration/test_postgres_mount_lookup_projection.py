"""End-to-end: register_mount slot_code uniqueness against real Postgres.

Third instance of the load-bearing single-stream-write +
projection-precondition pattern (alongside asset_location for
install_asset and mount_children for decommission_mount). The
register_mount handler reads proj_equipment_mount_lookup at
decide-time; if the slot_code already maps to an Active Mount, the
decider raises MountAlreadyExistsError carrying the pre-existing
mount_id.

Pins:
  - MountRegistered -> INSERT (slot_code, mount_id, registered_at)
  - MountDecommissioned -> DELETE row by mount_id (slot_code becomes
    available again)
  - register_mount with a slot_code already taken by an Active Mount
    raises MountAlreadyExistsError carrying the pre-existing mount_id
  - After decommission, the same slot_code can be re-registered
    cleanly (different mount_id, mount_lookup row points at the new
    one)
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.mount import MountAlreadyExistsError
from cora.equipment.features.decommission_mount import DecommissionMount
from cora.equipment.features.decommission_mount import bind as bind_decommission_mount
from cora.equipment.features.register_frame import RegisterFrame
from cora.equipment.features.register_frame import bind as bind_register_frame
from cora.equipment.features.register_mount import RegisterMount
from cora.equipment.features.register_mount import bind as bind_register_mount
from cora.equipment.projections.mount_lookup import load_mount_id_by_slot_code
from cora.infrastructure.kernel import Kernel
from tests.integration._equipment_helpers import drain_equipment_projections, placement
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 31, 9, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 31, 10, 30, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(pool: asyncpg.Pool, ids: list[UUID], now: datetime = _NOW) -> Kernel:
    return build_postgres_deps(pool, now=now, ids=ids)


async def _seed_frame(pool: asyncpg.Pool, frame_id: UUID) -> None:
    deps = _build_deps(pool, [frame_id, uuid4()])
    await bind_register_frame(deps)(
        RegisterFrame(
            name=f"frame-{frame_id}",
            parent_frame_id=None,
            placement=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_register_mount_inserts_slot_code_to_mount_id_row(
    db_pool: asyncpg.Pool,
) -> None:
    frame_id = uuid4()
    await _seed_frame(db_pool, frame_id)
    mount_id = uuid4()
    deps = _build_deps(db_pool, [mount_id, uuid4()])
    await bind_register_mount(deps)(
        RegisterMount(
            slot_code="02-BM-A-K-lookup-01",
            parent_mount_id=None,
            placement=placement(frame_id),
            drawing=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    assert await load_mount_id_by_slot_code(db_pool, "02-BM-A-K-lookup-01") == mount_id


@pytest.mark.integration
async def test_register_mount_rejects_colliding_slot_code(db_pool: asyncpg.Pool) -> None:
    """Load-bearing fitness: the handler reads mount_lookup at
    decide-time. A second register_mount with a slot_code already
    taken by an Active Mount surfaces MountAlreadyExistsError carrying
    the pre-existing mount_id; the second stream is never written."""
    frame_id = uuid4()
    await _seed_frame(db_pool, frame_id)
    first_mount_id = uuid4()
    deps = _build_deps(db_pool, [first_mount_id, uuid4()])
    await bind_register_mount(deps)(
        RegisterMount(
            slot_code="02-BM-B-K-collision",
            parent_mount_id=None,
            placement=placement(frame_id),
            drawing=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    second_mount_id = uuid4()
    deps = _build_deps(db_pool, [second_mount_id, uuid4()], now=_LATER)
    with pytest.raises(MountAlreadyExistsError) as info:
        await bind_register_mount(deps)(
            RegisterMount(
                slot_code="02-BM-B-K-collision",
                parent_mount_id=None,
                placement=placement(frame_id),
                drawing=None,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert info.value.mount_id == first_mount_id

    stored, version = await deps.event_store.load("Mount", second_mount_id)
    assert stored == []
    assert version == 0


@pytest.mark.integration
async def test_decommission_frees_slot_code_for_re_registration(
    db_pool: asyncpg.Pool,
) -> None:
    """A decommissioned mount's slot_code becomes available again: the
    mount_lookup row is deleted, and a fresh register_mount with the
    same slot_code succeeds (different mount_id)."""
    frame_id = uuid4()
    await _seed_frame(db_pool, frame_id)
    first_mount_id = uuid4()
    deps = _build_deps(db_pool, [first_mount_id, uuid4()])
    await bind_register_mount(deps)(
        RegisterMount(
            slot_code="02-BM-C-K-recycle",
            parent_mount_id=None,
            placement=placement(frame_id),
            drawing=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)
    assert await load_mount_id_by_slot_code(db_pool, "02-BM-C-K-recycle") == first_mount_id

    deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await bind_decommission_mount(deps)(
        DecommissionMount(mount_id=first_mount_id, reason="slot retired"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)
    assert await load_mount_id_by_slot_code(db_pool, "02-BM-C-K-recycle") is None

    second_mount_id = uuid4()
    deps = _build_deps(db_pool, [second_mount_id, uuid4()], now=_LATER)
    await bind_register_mount(deps)(
        RegisterMount(
            slot_code="02-BM-C-K-recycle",
            parent_mount_id=None,
            placement=placement(frame_id),
            drawing=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)
    assert await load_mount_id_by_slot_code(db_pool, "02-BM-C-K-recycle") == second_mount_id
