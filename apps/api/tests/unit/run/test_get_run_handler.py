"""Unit tests for the `get_run` query handler.

Mirrors `test_get_plan_handler.py`. Round-trip seed + get verifies
fold-on-read returns the started Run.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.config import Settings
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import (
    Allow,
    AllowAllAuthorize,
    AuthzResult,
    Deny,
    FixedIdGenerator,
    FrozenClock,
)
from cora.run import RunHandlers, UnauthorizedError, wire_run
from cora.run.aggregates.run import (
    Run,
    RunName,
    RunStatus,
)
from cora.run.aggregates.run.events import (
    RunStarted,
    event_type_name,
    to_payload,
)
from cora.run.features import get_run
from cora.run.features.get_run import GetRun

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_RUN_ID = UUID("01900000-0000-7000-8000-00000000ff01")
_PLAN_ID = UUID("01900000-0000-7000-8000-00000000ff02")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-00000000ff03")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(event_store: InMemoryEventStore | None = None) -> SharedDeps:
    settings = Settings(app_env="test")  # type: ignore[call-arg]
    return SharedDeps(
        settings=settings,
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_RUN_ID]),
        authorize=AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


async def _seed_run(
    store: InMemoryEventStore,
    run_id: UUID,
    *,
    plan_id: UUID,
    subject_id: UUID | None,
    name: str = "32-ID FlyScan",
) -> None:
    event = RunStarted(
        run_id=run_id,
        name=name,
        plan_id=plan_id,
        subject_id=subject_id,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=_CORRELATION_ID,
    )
    await store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=0,
        events=[new_event],
    )


@pytest.mark.unit
async def test_handler_returns_run_for_known_id_with_subject() -> None:
    """Round-trip: seed sample run + get."""
    store = InMemoryEventStore()
    await _seed_run(store, _RUN_ID, plan_id=_PLAN_ID, subject_id=_SUBJECT_ID)
    deps = _build_deps(event_store=store)
    handler = get_run.bind(deps)
    run = await handler(
        GetRun(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert run == Run(
        id=_RUN_ID,
        name=RunName("32-ID FlyScan"),
        plan_id=_PLAN_ID,
        subject_id=_SUBJECT_ID,
        status=RunStatus.RUNNING,
    )


@pytest.mark.unit
async def test_handler_returns_run_for_known_id_without_subject() -> None:
    """Calibration / dark-field run: subject_id=None."""
    store = InMemoryEventStore()
    await _seed_run(store, _RUN_ID, plan_id=_PLAN_ID, subject_id=None, name="Dark field")
    deps = _build_deps(event_store=store)
    handler = get_run.bind(deps)
    run = await handler(
        GetRun(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert run is not None
    assert run.subject_id is None


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_id() -> None:
    deps = _build_deps()
    handler = get_run.bind(deps)
    run = await handler(
        GetRun(run_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert run is None


class _RecordingAuthorize:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str, UUID]] = []

    async def __call__(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
    ) -> AuthzResult:
        self.calls.append((principal_id, command_name, conduit_id))
        return Allow()


class _DenyAllAuthorize:
    async def __call__(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
    ) -> AuthzResult:
        _ = (principal_id, command_name, conduit_id)
        return Deny(reason="denied for test")


@pytest.mark.unit
async def test_handler_authorizes_with_query_name_and_default_conduit() -> None:
    tracking = _RecordingAuthorize()
    deps = SharedDeps(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_RUN_ID]),
        authorize=tracking,
        event_store=InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )

    handler = get_run.bind(deps)
    await handler(
        GetRun(run_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert tracking.calls == [(_PRINCIPAL_ID, "GetRun", UUID(int=0))]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = SharedDeps(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_RUN_ID]),
        authorize=_DenyAllAuthorize(),
        event_store=InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )
    handler = get_run.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetRun(run_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
def test_wire_run_includes_get_run() -> None:
    deps = _build_deps()
    handlers = wire_run(deps)
    assert isinstance(handlers, RunHandlers)
    assert callable(handlers.get_run)
