"""Unit tests for the `return_subject` application handler.

Exercises the load+fold+decide+append flow against InMemoryEventStore.
Mirrors the prior 4b-c handler tests for the update-style pattern.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.subject import SubjectHandlers, UnauthorizedError, wire_subject
from cora.subject.aggregates.subject import (
    SubjectCannotReturnError,
    SubjectNotFoundError,
    SubjectStatus,
)
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
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.subject._asset_helper import seed_active_asset

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000005ab1")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be1")
_MOUNT_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be2")
_REMOVE_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be3")
_RETURN_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be4")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list."""
    return _build_deps_shared(
        ids=[
            _NEW_ID,
            _REGISTER_EVENT_ID,
            _MOUNT_EVENT_ID,
            _REMOVE_EVENT_ID,
            _RETURN_EVENT_ID,
        ],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _register_mount_remove(deps: Kernel) -> UUID:
    """Helper: register + mount + remove a subject and return its id.

    Skipping measure exercises the Mounted -> Removed -> terminal
    path; the terminal slices don't care which sub-path led to
    Removed.
    """
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
    return subject_id


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    """Update-style handlers return None."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_mount_remove(deps)

    result = await return_subject.bind(deps)(
        ReturnSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_subject_returned_event() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_mount_remove(deps)

    await return_subject.bind(deps)(
        ReturnSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Subject", subject_id)
    assert version == 4  # SubjectRegistered + SubjectMounted + SubjectRemoved + SubjectReturned
    returned = events[3]
    assert returned.event_type == "SubjectReturned"
    assert returned.payload == {
        "subject_id": str(subject_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert returned.event_id == _RETURN_EVENT_ID
    assert returned.metadata == {"command": "ReturnSubject"}
    assert returned.causation_id is None


@pytest.mark.unit
async def test_handler_raises_subject_not_found_when_subject_does_not_exist() -> None:
    """The decider's SubjectNotFoundError propagates unchanged."""
    deps = _build_deps()
    handler = return_subject.bind(deps)

    with pytest.raises(SubjectNotFoundError):
        await handler(
            ReturnSubject(subject_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_return_when_subject_not_yet_removed() -> None:
    """Strict semantics: returning a Mounted (not yet Removed) subject
    raises rather than no-ops. Tests the source-state guard via the
    handler."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
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

    handler = return_subject.bind(deps)
    with pytest.raises(SubjectCannotReturnError) as exc_info:
        await handler(
            ReturnSubject(subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.subject_id == subject_id
    assert exc_info.value.current_status is SubjectStatus.MOUNTED


@pytest.mark.unit
async def test_handler_raises_cannot_return_when_subject_already_returned() -> None:
    """Strict semantics: re-returning raises rather than no-ops."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_mount_remove(deps)

    handler = return_subject.bind(deps)
    await handler(
        ReturnSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(SubjectCannotReturnError) as exc_info:
        await handler(
            ReturnSubject(subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.subject_id == subject_id
    assert exc_info.value.current_status is SubjectStatus.RETURNED


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_mount_remove(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    handler = return_subject.bind(deny_deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            ReturnSubject(subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_mount_remove(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError):
        await return_subject.bind(deny_deps)(
            ReturnSubject(subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Subject", subject_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "SubjectRegistered",
        "SubjectMounted",
        "SubjectRemoved",
    ]


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_mount_remove(deps)

    await return_subject.bind(deps)(
        ReturnSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Subject", subject_id)
    assert events[3].causation_id == causation


@pytest.mark.unit
def test_wire_subject_includes_return_subject() -> None:
    deps = _build_deps()
    handlers = wire_subject(deps)
    assert isinstance(handlers, SubjectHandlers)
    assert callable(handlers.return_subject)
    # earlier-phase handlers still wired (regression guards)
    assert callable(handlers.register_subject)
    assert callable(handlers.mount_subject)
    assert callable(handlers.measure_subject)
    assert callable(handlers.remove_subject)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end check that causation_id survives the `with_tracing(bare)`
    chain in wire.py."""
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_mount_remove(deps)

    handlers = wire_subject(deps)
    await handlers.return_subject(
        ReturnSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Subject", subject_id)
    assert events[3].causation_id == causation
