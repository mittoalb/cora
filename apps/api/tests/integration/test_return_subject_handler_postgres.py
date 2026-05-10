"""End-to-end integration test: return_subject handler against real Postgres.

Mirrors the prior subject integration tests. Proves the bare handler
composes with PostgresEventStore for the Removed -> Returned terminal
transition.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.config import Settings
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FixedIdGenerator,
    FrozenClock,
)
from cora.infrastructure.postgres.event_store import PostgresEventStore
from cora.infrastructure.postgres.idempotency import PostgresIdempotencyStore
from cora.subject.features import (
    mount_subject,
    register_subject,
    remove_subject,
    return_subject,
)
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from cora.subject.features.remove_subject import RemoveSubject
from cora.subject.features.return_subject import ReturnSubject

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000054e1ec")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-00000054e1ed")
_MOUNT_EVENT_ID = UUID("01900000-0000-7000-8000-00000054e1ee")
_REMOVE_EVENT_ID = UUID("01900000-0000-7000-8000-00000054e1ef")
_RETURN_EVENT_ID = UUID("01900000-0000-7000-8000-00000054e1f0")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_return_subject_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = SharedDeps(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator(
            [
                _NEW_ID,
                _REGISTER_EVENT_ID,
                _MOUNT_EVENT_ID,
                _REMOVE_EVENT_ID,
                _RETURN_EVENT_ID,
            ]
        ),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )

    subject_id = await register_subject.bind(deps)(
        RegisterSubject(name="Sample-A1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await remove_subject.bind(deps)(
        RemoveSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await return_subject.bind(deps)(
        ReturnSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Subject", subject_id)
    assert version == 4
    assert [e.event_type for e in events] == [
        "SubjectRegistered",
        "SubjectMounted",
        "SubjectRemoved",
        "SubjectReturned",
    ]

    returned = events[3]
    assert returned.schema_version == 1
    assert returned.payload == {
        "subject_id": str(subject_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert returned.correlation_id == _CORRELATION_ID
    assert returned.causation_id is None
    assert returned.event_id == _RETURN_EVENT_ID
    assert returned.metadata == {"command": "ReturnSubject"}
    assert returned.occurred_at == _NOW
    assert returned.position > events[2].position
