"""Unit tests for the `store_subject` application handler.

Mirrors `test_return_subject_handler.py` for the Stored terminal slice.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.subject import SubjectHandlers, UnauthorizedError, wire_subject
from cora.subject.aggregates.subject import (
    SubjectCannotStoreError,
    SubjectNotFoundError,
    SubjectStatus,
)
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
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.subject._asset_helper import seed_active_asset

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000005ab1")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be1")
_MOUNT_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be2")
_REMOVE_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be3")
_STORE_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be4")
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
            _STORE_EVENT_ID,
        ],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _register_mount_remove(deps: Kernel) -> UUID:
    """Helper: register + mount + remove a subject and return its id."""
    subject_id = await register_subject.bind(deps)(
        RegisterSubject(name="Sample-A1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await seed_active_asset(deps.event_store, now=_NOW, correlation_id=_CORRELATION_ID)
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=asset_id),
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
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_mount_remove(deps)

    result = await store_subject.bind(deps)(
        StoreSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_subject_stored_event() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_mount_remove(deps)

    await store_subject.bind(deps)(
        StoreSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Subject", subject_id)
    assert version == 4
    stored = events[3]
    assert stored.event_type == "SubjectStored"
    assert stored.payload == {
        "subject_id": str(subject_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.event_id == _STORE_EVENT_ID
    assert stored.metadata == {"command": "StoreSubject"}
    assert stored.causation_id is None


@pytest.mark.unit
async def test_handler_raises_subject_not_found_when_subject_does_not_exist() -> None:
    deps = _build_deps()
    handler = store_subject.bind(deps)

    with pytest.raises(SubjectNotFoundError):
        await handler(
            StoreSubject(subject_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_store_when_subject_not_yet_removed() -> None:
    """Strict semantics: storing a Mounted (not yet Removed) subject raises."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await register_subject.bind(deps)(
        RegisterSubject(name="Sample-A1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await seed_active_asset(deps.event_store, now=_NOW, correlation_id=_CORRELATION_ID)
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = store_subject.bind(deps)
    with pytest.raises(SubjectCannotStoreError) as exc_info:
        await handler(
            StoreSubject(subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.subject_id == subject_id
    assert exc_info.value.current_status is SubjectStatus.MOUNTED


@pytest.mark.unit
async def test_handler_raises_cannot_store_when_subject_already_stored() -> None:
    """Strict semantics: re-storing raises."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_mount_remove(deps)

    handler = store_subject.bind(deps)
    await handler(
        StoreSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(SubjectCannotStoreError) as exc_info:
        await handler(
            StoreSubject(subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.subject_id == subject_id
    assert exc_info.value.current_status is SubjectStatus.STORED


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_mount_remove(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    handler = store_subject.bind(deny_deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            StoreSubject(subject_id=subject_id),
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
        await store_subject.bind(deny_deps)(
            StoreSubject(subject_id=subject_id),
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

    await store_subject.bind(deps)(
        StoreSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Subject", subject_id)
    assert events[3].causation_id == causation


@pytest.mark.unit
def test_wire_subject_includes_store_subject() -> None:
    deps = _build_deps()
    handlers = wire_subject(deps)
    assert isinstance(handlers, SubjectHandlers)
    assert callable(handlers.store_subject)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_mount_remove(deps)

    handlers = wire_subject(deps)
    await handlers.store_subject(
        StoreSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Subject", subject_id)
    assert events[3].causation_id == causation
