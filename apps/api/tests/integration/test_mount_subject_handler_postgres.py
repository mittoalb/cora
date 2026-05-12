"""End-to-end integration test: mount_subject handler against real Postgres.

Mirrors the update-style integration tests for Access. Proves the bare
handler composes with PostgresEventStore: load + fold reads back the
SubjectRegistered event, the evolver folds to status=Received, the
decider permits the transition, and SubjectMounted lands at version 2.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FixedIdGenerator,
    FrozenClock,
)
from cora.infrastructure.postgres.event_store import PostgresEventStore
from cora.infrastructure.postgres.idempotency import PostgresIdempotencyStore
from cora.subject.features import mount_subject, register_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000054b2ec")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-00000054b2ed")
_MOUNT_EVENT_ID = UUID("01900000-0000-7000-8000-00000054b2ee")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_mount_subject_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = Kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_NEW_ID, _REGISTER_EVENT_ID, _MOUNT_EVENT_ID]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )

    # Register a subject (consumes _NEW_ID + _REGISTER_EVENT_ID).
    subject_id = await register_subject.bind(deps)(
        RegisterSubject(name="Sample-A1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert subject_id == _NEW_ID

    # Mount it (consumes _MOUNT_EVENT_ID).
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Subject", subject_id)
    assert version == 2
    assert len(events) == 2

    mounted = events[1]
    assert mounted.event_type == "SubjectMounted"
    assert mounted.schema_version == 1
    assert mounted.payload == {
        "subject_id": str(subject_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert mounted.correlation_id == _CORRELATION_ID
    assert mounted.causation_id is None
    assert mounted.event_id == _MOUNT_EVENT_ID
    assert mounted.metadata == {"command": "MountSubject"}
    assert mounted.occurred_at == _NOW
    assert mounted.position > events[0].position
