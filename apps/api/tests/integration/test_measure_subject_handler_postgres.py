"""End-to-end integration test: measure_subject handler against real Postgres.

Mirrors `test_mount_subject_handler_postgres.py`. Proves the bare
handler composes with PostgresEventStore: load + fold reads back the
SubjectRegistered + SubjectMounted prefix, the evolver folds to
status=Mounted, the decider permits the transition, and SubjectMeasured
lands at version 3.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.subject.features import measure_subject, mount_subject, register_subject
from cora.subject.features.measure_subject import MeasureSubject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from tests.integration._helpers import build_postgres_deps
from tests.unit.subject._helpers import seed_active_asset

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000054c2ec")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-00000054c2ed")
_MOUNT_EVENT_ID = UUID("01900000-0000-7000-8000-00000054c2ee")
_MEASURE_EVENT_ID = UUID("01900000-0000-7000-8000-00000054c2ef")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_measure_subject_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _MOUNT_EVENT_ID, _MEASURE_EVENT_ID],
    )

    # Register + mount the subject (consumes the first three event ids).
    subject_id = await register_subject.bind(deps)(
        RegisterSubject(name="Sample-A1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert subject_id == _NEW_ID
    asset_id = await seed_active_asset(deps.event_store, now=_NOW, correlation_id=_CORRELATION_ID)
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=asset_id, reason=""),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Measure it (consumes _MEASURE_EVENT_ID).
    await measure_subject.bind(deps)(
        MeasureSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Subject", subject_id)
    assert version == 3
    assert len(events) == 3

    measured = events[2]
    assert measured.event_type == "SubjectMeasured"
    assert measured.schema_version == 1
    assert measured.payload == {
        "subject_id": str(subject_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert measured.correlation_id == _CORRELATION_ID
    assert measured.causation_id is None
    assert measured.event_id == _MEASURE_EVENT_ID
    assert measured.metadata == {"command": "MeasureSubject"}
    assert measured.occurred_at == _NOW
    assert measured.position > events[1].position
