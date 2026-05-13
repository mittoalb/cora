"""Integration test: get_subject handler against real Postgres.

Mirrors `test_get_actor_handler_postgres.py`. Round-trips through
the full lifecycle (register + mount + measure + remove) verify that
fold-on-read against PostgresEventStore correctly reproduces the
state every transition produced.
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
from cora.subject.aggregates.subject import SubjectName, SubjectStatus
from cora.subject.features import (
    get_subject,
    measure_subject,
    mount_subject,
    register_subject,
    remove_subject,
)
from cora.subject.features.get_subject import GetSubject
from cora.subject.features.measure_subject import MeasureSubject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from cora.subject.features.remove_subject import RemoveSubject
from tests.unit.subject._asset_helper import seed_active_asset

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_get_subject_loads_received_state_from_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    subject_id = UUID("01900000-0000-7000-8000-00000054f1ec")
    register_event_id = UUID("01900000-0000-7000-8000-00000054f1ed")
    deps = Kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([subject_id, register_event_id]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )

    await register_subject.bind(deps)(
        RegisterSubject(name="Sample-A1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    subject = await get_subject.bind(deps)(
        GetSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert subject is not None
    assert subject.id == subject_id
    assert subject.name == SubjectName("Sample-A1")
    assert subject.status is SubjectStatus.RECEIVED


@pytest.mark.integration
async def test_get_subject_loads_full_lifecycle_state_from_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Pinned: fold-on-read against the real event store must agree
    with the write-side evolver after register + mount + measure +
    remove. Regression guard for any future evolver edit that
    diverges from the write path under real persistence."""
    subject_id = UUID("01900000-0000-7000-8000-00000054f2ec")
    register_event_id = UUID("01900000-0000-7000-8000-00000054f2ed")
    mount_event_id = UUID("01900000-0000-7000-8000-00000054f2ee")
    measure_event_id = UUID("01900000-0000-7000-8000-00000054f2ef")
    remove_event_id = UUID("01900000-0000-7000-8000-00000054f2f0")
    deps = Kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator(
            [
                subject_id,
                register_event_id,
                mount_event_id,
                measure_event_id,
                remove_event_id,
            ]
        ),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )

    await register_subject.bind(deps)(
        RegisterSubject(name="Sample-A2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await seed_active_asset(
        deps.event_store, now=_NOW, correlation_id=_CORRELATION_ID
    )
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=asset_id),
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

    subject = await get_subject.bind(deps)(
        GetSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert subject is not None
    assert subject.status is SubjectStatus.REMOVED
    assert subject.name == SubjectName("Sample-A2")
