"""Unit tests for the `stop_run` application handler.

Mirror of `test_abort_run_handler.py` (string-payload shape:
run_id + reason). Strict-not-idempotent, append-once-on-success.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.config import Settings
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    AuthzResult,
    Deny,
    FixedIdGenerator,
    FrozenClock,
)
from cora.run import RunHandlers, UnauthorizedError, wire_run
from cora.run.aggregates.run import (
    InvalidRunStopReasonError,
    RunCannotStopError,
    RunNotFoundError,
)
from cora.run.aggregates.run.events import (
    RunStarted,
    RunStopped,
    event_type_name,
    to_payload,
)
from cora.run.features import stop_run
from cora.run.features.stop_run import StopRun

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_RUN_ID = UUID("01900000-0000-7000-8000-00000000fe01")
_STOPPED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000fe02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


class DenyAllAuthorize:
    async def __call__(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
    ) -> AuthzResult:
        _ = (principal_id, command_name, conduit_id)
        return Deny(reason="denied for test")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    settings = Settings(app_env="test")  # type: ignore[call-arg]
    return Kernel(
        settings=settings,
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_STOPPED_EVENT_ID]),
        authorize=DenyAllAuthorize() if deny else AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


async def _seed_run_started(store: InMemoryEventStore, run_id: UUID) -> None:
    event = RunStarted(
        run_id=run_id,
        name="32-ID FlyScan",
        plan_id=uuid4(),
        subject_id=uuid4(),
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
    await store.append(stream_type="Run", stream_id=run_id, expected_version=0, events=[new_event])


async def _seed_run_stopped(store: InMemoryEventStore, run_id: UUID) -> None:
    await _seed_run_started(store, run_id)
    stopped = RunStopped(run_id=run_id, reason="prior stop", occurred_at=_NOW)
    new_event = to_new_event(
        event_type=event_type_name(stopped),
        payload=to_payload(stopped),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StopRun",
        correlation_id=_CORRELATION_ID,
    )
    await store.append(stream_type="Run", stream_id=run_id, expected_version=1, events=[new_event])


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    deps = _build_deps(event_store=store)

    result = await stop_run.bind(deps)(
        StopRun(run_id=_RUN_ID, reason="hit time budget cleanly"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_run_stopped_event_with_trimmed_reason() -> None:
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    deps = _build_deps(event_store=store)

    await stop_run.bind(deps)(
        StopRun(run_id=_RUN_ID, reason="  scan complete; ending early  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Run", _RUN_ID)
    assert version == 2
    assert [e.event_type for e in events] == ["RunStarted", "RunStopped"]
    stopped = events[1]
    assert stopped.event_id == _STOPPED_EVENT_ID
    assert stopped.metadata == {"command": "StopRun"}
    assert stopped.payload["reason"] == "scan complete; ending early"


@pytest.mark.unit
async def test_handler_raises_run_not_found_when_run_does_not_exist() -> None:
    deps = _build_deps()
    handler = stop_run.bind(deps)

    with pytest.raises(RunNotFoundError):
        await handler(
            StopRun(run_id=_RUN_ID, reason="X"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_reason_for_whitespace_only() -> None:
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    deps = _build_deps(event_store=store)

    with pytest.raises(InvalidRunStopReasonError):
        await stop_run.bind(deps)(
            StopRun(run_id=_RUN_ID, reason="   "),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_stop_when_already_stopped() -> None:
    """Strict-not-idempotent: re-stopping raises."""
    store = InMemoryEventStore()
    await _seed_run_stopped(store, _RUN_ID)
    deps = _build_deps(event_store=store)

    with pytest.raises(RunCannotStopError):
        await stop_run.bind(deps)(
            StopRun(run_id=_RUN_ID, reason="X"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    deny_deps = _build_deps(event_store=store, deny=True)

    with pytest.raises(UnauthorizedError) as exc_info:
        await stop_run.bind(deny_deps)(
            StopRun(run_id=_RUN_ID, reason="X"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    await _seed_run_started(store, _RUN_ID)
    deps = _build_deps(event_store=store)

    await stop_run.bind(deps)(
        StopRun(run_id=_RUN_ID, reason="X"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Run", _RUN_ID)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_run_includes_stop_run() -> None:
    deps = _build_deps()
    handlers = wire_run(deps)
    assert isinstance(handlers, RunHandlers)
    assert callable(handlers.stop_run)
