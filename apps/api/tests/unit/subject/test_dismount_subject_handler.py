"""Unit tests for the `dismount_subject` application handler (Phase 4f).

Mirrors `test_mount_subject_handler.py` for the inverse direction:
clears `mounted_on_asset_id`, returns status to Received.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.subject import SubjectHandlers, UnauthorizedError, wire_subject
from cora.subject.aggregates.subject import (
    SubjectCannotDismountError,
    SubjectNotFoundError,
    SubjectStatus,
)
from cora.subject.features import dismount_subject, mount_subject, register_subject
from cora.subject.features.dismount_subject import DismountSubject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.subject._asset_helper import seed_active_asset

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-0000000d04a1")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-0000000d04b1")
_MOUNT_EVENT_ID = UUID("01900000-0000-7000-8000-0000000d04b2")
_DISMOUNT_EVENT_ID = UUID("01900000-0000-7000-8000-0000000d04b3")
_REMOUNT_EVENT_ID = UUID("01900000-0000-7000-8000-0000000d04b4")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[
            _NEW_ID,
            _REGISTER_EVENT_ID,
            _MOUNT_EVENT_ID,
            _DISMOUNT_EVENT_ID,
            _REMOUNT_EVENT_ID,
        ],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _register_subject(deps: Kernel) -> UUID:
    return await register_subject.bind(deps)(
        RegisterSubject(name="Sample-A1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _mount(deps: Kernel, subject_id: UUID, asset_id: UUID) -> None:
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=asset_id, reason="setup"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await seed_active_asset(store, now=_NOW, correlation_id=_CORRELATION_ID)
    subject_id = await _register_subject(deps)
    await _mount(deps, subject_id, asset_id)

    result = await dismount_subject.bind(deps)(
        DismountSubject(subject_id=subject_id, reason="run complete"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_subject_dismounted_event() -> None:
    """Pinned: payload carries from_asset_id (read from prior state)
    and reason (carried from command). Mirrors AssetRelocated's
    self-contained-audit pattern."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await seed_active_asset(store, now=_NOW, correlation_id=_CORRELATION_ID)
    subject_id = await _register_subject(deps)
    await _mount(deps, subject_id, asset_id)

    await dismount_subject.bind(deps)(
        DismountSubject(subject_id=subject_id, reason="run complete"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Subject", subject_id)
    assert version == 3  # registered + mounted + dismounted
    dismounted = events[-1]
    assert dismounted.event_type == "SubjectDismounted"
    assert dismounted.payload["from_asset_id"] == str(asset_id)
    assert dismounted.payload["reason"] == "run complete"
    assert dismounted.metadata == {"command": "DismountSubject"}


@pytest.mark.unit
async def test_handler_raises_subject_not_found_when_subject_does_not_exist() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = dismount_subject.bind(deps)

    with pytest.raises(SubjectNotFoundError):
        await handler(
            DismountSubject(subject_id=uuid4(), reason="x"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_dismount_when_subject_only_received() -> None:
    """Strict-not-idempotent: dismounting a never-mounted subject raises."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_subject(deps)

    handler = dismount_subject.bind(deps)
    with pytest.raises(SubjectCannotDismountError) as exc_info:
        await handler(
            DismountSubject(subject_id=subject_id, reason="x"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.subject_id == subject_id
    assert exc_info.value.current_status is SubjectStatus.RECEIVED


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await seed_active_asset(store, now=_NOW, correlation_id=_CORRELATION_ID)
    subject_id = await _register_subject(deps)
    await _mount(deps, subject_id, asset_id)

    deny_deps = _build_deps(event_store=store, deny=True)
    handler = dismount_subject.bind(deny_deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            DismountSubject(subject_id=subject_id, reason="x"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Stream still has only register + mount; no dismount appended.
    events, version = await store.load("Subject", subject_id)
    assert version == 2
    assert events[-1].event_type == "SubjectMounted"


@pytest.mark.unit
async def test_handler_propagates_causation_id() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await seed_active_asset(store, now=_NOW, correlation_id=_CORRELATION_ID)
    subject_id = await _register_subject(deps)
    await _mount(deps, subject_id, asset_id)

    await dismount_subject.bind(deps)(
        DismountSubject(subject_id=subject_id, reason="x"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Subject", subject_id)
    assert events[-1].causation_id == causation


@pytest.mark.unit
async def test_remount_cycle_after_dismount() -> None:
    """Pin the multi-stage workflow: mount -> dismount -> mount cycle
    works end-to-end at the handler layer. Subject status returns to
    Received after dismount; subsequent mount succeeds."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await seed_active_asset(store, now=_NOW, correlation_id=_CORRELATION_ID)
    subject_id = await _register_subject(deps)
    await _mount(deps, subject_id, asset_id)
    await dismount_subject.bind(deps)(
        DismountSubject(subject_id=subject_id, reason="moving"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Re-mount on same Asset (would also work for different Asset).
    await _mount(deps, subject_id, asset_id)

    events, version = await store.load("Subject", subject_id)
    assert version == 4
    assert [e.event_type for e in events] == [
        "SubjectRegistered",
        "SubjectMounted",
        "SubjectDismounted",
        "SubjectMounted",
    ]


@pytest.mark.unit
def test_wire_subject_includes_dismount_subject() -> None:
    deps = _build_deps()
    handlers = wire_subject(deps)
    assert isinstance(handlers, SubjectHandlers)
    assert callable(handlers.dismount_subject)
