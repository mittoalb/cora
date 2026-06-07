"""End-to-end integration test: discard_subject handler against real Postgres.

Mirrors `test_return_subject_handler_postgres.py` for the Discarded
terminal slice.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.subject.features import (
    discard_subject,
    mount_subject,
    register_subject,
    remove_subject,
)
from cora.subject.features.discard_subject import DiscardSubject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from cora.subject.features.remove_subject import RemoveSubject
from tests.integration._helpers import build_postgres_deps
from tests.unit.subject._helpers import seed_active_asset

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000054e3ec")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-00000054e3ed")
_MOUNT_EVENT_ID = UUID("01900000-0000-7000-8000-00000054e3ee")
_REMOVE_EVENT_ID = UUID("01900000-0000-7000-8000-00000054e3ef")
_DISCARD_EVENT_ID = UUID("01900000-0000-7000-8000-00000054e3f0")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_discard_subject_persists_event_to_postgres(
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
            _DISCARD_EVENT_ID,
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

    await discard_subject.bind(deps)(
        DiscardSubject(subject_id=subject_id, reason="contaminated; biohazard incinerator"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Subject", subject_id)
    assert version == 4
    assert [e.event_type for e in events] == [
        "SubjectRegistered",
        "SubjectMounted",
        "SubjectRemoved",
        "SubjectDiscarded",
    ]

    discarded = events[3]
    assert discarded.payload == {
        "subject_id": str(subject_id),
        "reason": "contaminated; biohazard incinerator",
        "occurred_at": _NOW.isoformat(),
        "discarded_by": str(_PRINCIPAL_ID),
    }
    assert discarded.event_id == _DISCARD_EVENT_ID
    assert discarded.metadata == {"command": "DiscardSubject"}
