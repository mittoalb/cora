"""End-to-end integration test: store_subject handler against real Postgres.

Mirrors `test_return_subject_handler_postgres.py` for the Stored
terminal slice.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.subject.features import (
    mount_subject,
    register_subject,
    remove_subject,
    store_subject,
)
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from cora.subject.features.remove_subject import RemoveSubject
from cora.subject.features.store_subject import StoreSubject
from tests.integration._helpers import build_postgres_deps
from tests.unit.subject._helpers import seed_active_asset

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000054e2ec")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-00000054e2ed")
_MOUNT_EVENT_ID = UUID("01900000-0000-7000-8000-00000054e2ee")
_REMOVE_EVENT_ID = UUID("01900000-0000-7000-8000-00000054e2ef")
_STORE_EVENT_ID = UUID("01900000-0000-7000-8000-00000054e2f0")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_store_subject_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            _NEW_ID,
            _REGISTER_EVENT_ID,
            _MOUNT_EVENT_ID,
            _REMOVE_EVENT_ID,
            _STORE_EVENT_ID,
        ],
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

    await store_subject.bind(deps)(
        StoreSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Subject", subject_id)
    assert version == 4
    assert [e.event_type for e in events] == [
        "SubjectRegistered",
        "SubjectMounted",
        "SubjectRemoved",
        "SubjectStored",
    ]

    stored = events[3]
    assert stored.payload == {
        "subject_id": str(subject_id),
        "occurred_at": _NOW.isoformat(),
        "stored_by": str(_PRINCIPAL_ID),
    }
    assert stored.event_id == _STORE_EVENT_ID
    assert stored.metadata == {"command": "StoreSubject"}
