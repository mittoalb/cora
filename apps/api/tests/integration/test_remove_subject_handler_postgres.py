"""End-to-end integration test: remove_subject handler against real Postgres.

Mirrors `test_mount_subject_handler_postgres.py`. Two scenarios cover
the multi-source-state guard (Mounted -> Removed and Measured ->
Removed); both are exercised against real Postgres so the
load+fold+decide+append cycle is validated for both source states with
the real event store.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.subject.features import (
    measure_subject,
    mount_subject,
    register_subject,
    remove_subject,
)
from cora.subject.features.measure_subject import MeasureSubject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from cora.subject.features.remove_subject import RemoveSubject
from tests.integration._helpers import build_postgres_deps
from tests.unit.subject._helpers import seed_active_asset

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_remove_subject_persists_event_from_mounted_state(
    db_pool: asyncpg.Pool,
) -> None:
    """Mounted -> Removed (skipping measure). Operator-changed-mind path."""
    new_id = UUID("01900000-0000-7000-8000-00000054d1ec")
    register_event_id = UUID("01900000-0000-7000-8000-00000054d1ed")
    mount_event_id = UUID("01900000-0000-7000-8000-00000054d1ee")
    remove_event_id = UUID("01900000-0000-7000-8000-00000054d1ef")
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[new_id, register_event_id, mount_event_id, remove_event_id],
    )

    subject_id = await register_subject.bind(deps)(
        RegisterSubject(name="Sample-A1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await seed_active_asset(deps.event_store, now=_NOW, correlation_id=_CORRELATION_ID)
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=asset_id, reason=""),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await remove_subject.bind(deps)(
        RemoveSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Subject", subject_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "SubjectRegistered",
        "SubjectMounted",
        "SubjectRemoved",
    ]
    removed = events[2]
    assert removed.payload == {
        "subject_id": str(subject_id),
        "occurred_at": _NOW.isoformat(),
        "removed_by": str(_PRINCIPAL_ID),
    }
    assert removed.event_id == remove_event_id
    assert removed.metadata == {"command": "RemoveSubject"}


@pytest.mark.integration
async def test_remove_subject_persists_event_from_measured_state(
    db_pool: asyncpg.Pool,
) -> None:
    """Full happy path: register + mount + measure + remove."""
    new_id = UUID("01900000-0000-7000-8000-00000054d2ec")
    register_event_id = UUID("01900000-0000-7000-8000-00000054d2ed")
    mount_event_id = UUID("01900000-0000-7000-8000-00000054d2ee")
    measure_event_id = UUID("01900000-0000-7000-8000-00000054d2ef")
    remove_event_id = UUID("01900000-0000-7000-8000-00000054d2f0")
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            new_id,
            register_event_id,
            mount_event_id,
            measure_event_id,
            remove_event_id,
        ],
    )

    subject_id = await register_subject.bind(deps)(
        RegisterSubject(name="Sample-A2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await seed_active_asset(deps.event_store, now=_NOW, correlation_id=_CORRELATION_ID)
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=asset_id, reason=""),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await measure_subject.bind(deps)(
        MeasureSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await remove_subject.bind(deps)(
        RemoveSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Subject", subject_id)
    assert version == 4
    assert [e.event_type for e in events] == [
        "SubjectRegistered",
        "SubjectMounted",
        "SubjectMeasured",
        "SubjectRemoved",
    ]
    removed = events[3]
    assert removed.event_id == remove_event_id
    assert removed.metadata == {"command": "RemoveSubject"}
