"""End-to-end integration test: dismount_subject handler against real Postgres (Phase 4f).

Round-trips the multi-stage workflow: register -> mount -> dismount
-> remount. Verifies SubjectDismounted event lands with the
from_asset_id from prior state and the SubjectStatus returns to
Received via the evolver, allowing re-mount.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.subject.features import dismount_subject, mount_subject, register_subject
from cora.subject.features.dismount_subject import DismountSubject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from tests.integration._helpers import build_postgres_deps
from tests.unit.subject._asset_helper import seed_active_asset

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_dismount_then_remount_round_trip_against_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Mount -> dismount -> mount cycles through Postgres. Final
    stream has 4 events; the dismount payload carries the from_asset_id
    from the prior Mounted state."""
    subject_id = UUID("01900000-0000-7000-8000-0000004f0001")
    register_event_id = UUID("01900000-0000-7000-8000-0000004f0011")
    mount_event_id = UUID("01900000-0000-7000-8000-0000004f0012")
    dismount_event_id = UUID("01900000-0000-7000-8000-0000004f0013")
    remount_event_id = UUID("01900000-0000-7000-8000-0000004f0014")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            subject_id,
            register_event_id,
            mount_event_id,
            dismount_event_id,
            remount_event_id,
        ],
    )

    asset_id = await seed_active_asset(deps.event_store, now=_NOW, correlation_id=_CORRELATION_ID)

    await register_subject.bind(deps)(
        RegisterSubject(name="Sample-A1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=asset_id, reason="alignment"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await dismount_subject.bind(deps)(
        DismountSubject(subject_id=subject_id, reason="moving to detector"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=asset_id, reason="loaded for scan"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Subject", subject_id)
    assert version == 4
    assert [e.event_type for e in events] == [
        "SubjectRegistered",
        "SubjectMounted",
        "SubjectDismounted",
        "SubjectMounted",
    ]
    dismounted = events[2]
    assert dismounted.payload["from_asset_id"] == str(asset_id)
    assert dismounted.payload["reason"] == "moving to detector"
    assert dismounted.metadata == {"command": "DismountSubject"}
