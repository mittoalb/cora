"""Unit tests for the `measure_subject` application handler.

Exercises the load+fold+decide+append flow against InMemoryEventStore.
Mirrors `test_mount_subject_handler.py` for the update-style pattern.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.ports import ConcurrencyError
from cora.subject import SubjectHandlers, UnauthorizedError, wire_subject
from cora.subject.aggregates.subject import (
    SubjectCannotMeasureError,
    SubjectNotFoundError,
    SubjectStatus,
)
from cora.subject.features import measure_subject, mount_subject, register_subject
from cora.subject.features.measure_subject import MeasureSubject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.subject._asset_helper import seed_active_asset

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000005ab1")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be1")
_MOUNT_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be2")
_MEASURE_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be3")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list."""
    return _build_deps_shared(
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _MOUNT_EVENT_ID, _MEASURE_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _register_and_mount(deps: Kernel) -> UUID:
    """Helper: register + mount a subject and return its id."""
    register_handler = register_subject.bind(deps)
    subject_id = await register_handler(
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
    return subject_id


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    """Update-style handlers return None. Pinned because returning
    anything else would break route / MCP layers that rely on
    `await handler(...)` not yielding a value."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_and_mount(deps)

    result = await measure_subject.bind(deps)(
        MeasureSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_subject_measured_event() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_and_mount(deps)

    await measure_subject.bind(deps)(
        MeasureSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Subject", subject_id)
    assert version == 3  # SubjectRegistered + SubjectMounted + SubjectMeasured
    assert len(events) == 3
    measured = events[2]
    assert measured.event_type == "SubjectMeasured"
    assert measured.payload == {
        "subject_id": str(subject_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert measured.event_id == _MEASURE_EVENT_ID
    assert measured.metadata == {"command": "MeasureSubject"}
    assert measured.causation_id is None


@pytest.mark.unit
async def test_handler_raises_subject_not_found_when_subject_does_not_exist() -> None:
    """The decider's SubjectNotFoundError propagates unchanged through
    the handler — the route maps it to 404."""
    deps = _build_deps()
    handler = measure_subject.bind(deps)

    with pytest.raises(SubjectNotFoundError):
        await handler(
            MeasureSubject(subject_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_measure_when_subject_only_received() -> None:
    """Strict semantics: measuring a Received (not yet Mounted) subject
    raises rather than no-ops. Tests the decider's source-state guard
    via the handler."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    register_handler = register_subject.bind(deps)
    subject_id = await register_handler(
        RegisterSubject(name="Sample-A1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = measure_subject.bind(deps)
    with pytest.raises(SubjectCannotMeasureError) as exc_info:
        await handler(
            MeasureSubject(subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.subject_id == subject_id
    assert exc_info.value.current_status is SubjectStatus.RECEIVED


@pytest.mark.unit
async def test_handler_raises_cannot_measure_when_subject_already_measured() -> None:
    """Strict semantics: re-measuring raises rather than no-ops."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_and_mount(deps)

    handler = measure_subject.bind(deps)
    await handler(
        MeasureSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(SubjectCannotMeasureError) as exc_info:
        await handler(
            MeasureSubject(subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.subject_id == subject_id
    assert exc_info.value.current_status is SubjectStatus.MEASURED


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    """Authz check fires before the load+fold path runs."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_and_mount(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    handler = measure_subject.bind(deny_deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            MeasureSubject(subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_and_mount(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError):
        await measure_subject.bind(deny_deps)(
            MeasureSubject(subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Stream still has only the register + mount events.
    events, version = await store.load("Subject", subject_id)
    assert version == 2
    assert [e.event_type for e in events] == ["SubjectRegistered", "SubjectMounted"]


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_and_mount(deps)

    await measure_subject.bind(deps)(
        MeasureSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Subject", subject_id)
    assert events[2].causation_id == causation


@pytest.mark.unit
def test_wire_subject_includes_measure_subject() -> None:
    deps = _build_deps()
    handlers = wire_subject(deps)
    assert isinstance(handlers, SubjectHandlers)
    assert callable(handlers.measure_subject)
    # earlier-phase handlers still wired (regression guards)
    assert callable(handlers.register_subject)
    assert callable(handlers.mount_subject)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end check that causation_id survives the `with_tracing(bare)`
    chain in wire.py. (No idempotency wrap on update-style commands.)"""
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_and_mount(deps)

    handlers = wire_subject(deps)
    await handlers.measure_subject(
        MeasureSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Subject", subject_id)
    assert events[2].causation_id == causation


# Suppress pyright's complaint about ConcurrencyError being unused.
_ = ConcurrencyError
