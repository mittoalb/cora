"""Unit tests for the `mount_subject` application handler.

Exercises the load+fold+decide+append flow against InMemoryEventStore.
Mirrors `test_deactivate_handler.py` for the update-style pattern, plus
the cross-aggregate-context pre-load (Asset) per the start_run pattern.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import AssetNotFoundError
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import ConcurrencyError
from cora.subject import SubjectHandlers, UnauthorizedError, wire_subject
from cora.subject.aggregates.subject import (
    SubjectCannotMountError,
    SubjectMountTargetUnavailableError,
    SubjectNotFoundError,
    SubjectStatus,
)
from cora.subject.features import mount_subject, register_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.subject._helpers import seed_active_asset

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000005ab1")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be1")
_MOUNT_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be2")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin per-file wrapper preserving this file's `_NOW` + ID list."""
    return _build_deps_shared(
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _MOUNT_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _register_subject(deps: Kernel) -> UUID:
    """Helper: register a subject and return its id."""
    handler = register_subject.bind(deps)
    return await handler(
        RegisterSubject(name="Sample-A1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_asset(store: InMemoryEventStore, *, activated: bool = True) -> UUID:
    """Thin per-file wrapper around the shared `seed_active_asset` that
    pins this file's `_NOW` + `_CORRELATION_ID`."""
    return await seed_active_asset(
        store, now=_NOW, correlation_id=_CORRELATION_ID, activated=activated
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    """Update-style handlers return None (no new id; mutation is the side
    effect)."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_subject(deps)
    asset_id = await _seed_asset(store)

    result = await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=asset_id, reason=""),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_subject_mounted_event() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_subject(deps)
    asset_id = await _seed_asset(store)

    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=asset_id, reason=""),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Subject", subject_id)
    assert version == 2  # SubjectRegistered + SubjectMounted
    assert len(events) == 2
    mounted = events[1]
    assert mounted.event_type == "SubjectMounted"
    assert mounted.payload == {
        "subject_id": str(subject_id),
        "asset_id": str(asset_id),
        "reason": "",
        "occurred_at": _NOW.isoformat(),
        "mounted_by": str(_PRINCIPAL_ID),
    }
    assert mounted.event_id == _MOUNT_EVENT_ID
    assert mounted.metadata == {"command": "MountSubject"}
    assert mounted.causation_id is None


@pytest.mark.unit
async def test_handler_raises_subject_not_found_when_subject_does_not_exist() -> None:
    """The decider's SubjectNotFoundError propagates unchanged through
    the handler — the route maps it to 404."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _seed_asset(store)
    handler = mount_subject.bind(deps)

    with pytest.raises(SubjectNotFoundError):
        await handler(
            MountSubject(subject_id=uuid4(), asset_id=asset_id, reason=""),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_asset_not_found_when_asset_does_not_exist() -> None:
    """The handler's load_asset returning None propagates as
    AssetNotFoundError — Equipment's routes map it to 404."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_subject(deps)

    handler = mount_subject.bind(deps)
    with pytest.raises(AssetNotFoundError):
        await handler(
            MountSubject(subject_id=subject_id, asset_id=uuid4(), reason=""),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_when_asset_not_active() -> None:
    """Asset that exists but is still Commissioned (not yet activated)
    triggers SubjectMountTargetUnavailableError -> 409."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_subject(deps)
    asset_id = await _seed_asset(store, activated=False)

    handler = mount_subject.bind(deps)
    with pytest.raises(SubjectMountTargetUnavailableError) as exc_info:
        await handler(
            MountSubject(subject_id=subject_id, asset_id=asset_id, reason=""),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.subject_id == subject_id
    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.current_lifecycle == "Commissioned"


@pytest.mark.unit
async def test_handler_raises_cannot_mount_when_subject_already_mounted() -> None:
    """Strict semantics: re-mount raises rather than no-ops."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_subject(deps)
    asset_id = await _seed_asset(store)

    handler = mount_subject.bind(deps)
    await handler(
        MountSubject(subject_id=subject_id, asset_id=asset_id, reason=""),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(SubjectCannotMountError) as exc_info:
        await handler(
            MountSubject(subject_id=subject_id, asset_id=asset_id, reason=""),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.subject_id == subject_id
    assert exc_info.value.current_status is SubjectStatus.MOUNTED


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    """Authz check fires before the load+fold path runs."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_subject(deps)
    asset_id = await _seed_asset(store)

    deny_deps = _build_deps(event_store=store, deny=True)
    handler = mount_subject.bind(deny_deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            MountSubject(subject_id=subject_id, asset_id=asset_id, reason=""),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_subject(deps)
    asset_id = await _seed_asset(store)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError):
        await mount_subject.bind(deny_deps)(
            MountSubject(subject_id=subject_id, asset_id=asset_id, reason=""),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Stream still has only the SubjectRegistered event.
    events, version = await store.load("Subject", subject_id)
    assert version == 1
    assert len(events) == 1
    assert events[0].event_type == "SubjectRegistered"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_subject(deps)
    asset_id = await _seed_asset(store)

    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=asset_id, reason=""),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Subject", subject_id)
    assert events[1].causation_id == causation


@pytest.mark.unit
async def test_handler_uses_optimistic_concurrency_check() -> None:
    """Second mount fails the decider's status guard, not the
    concurrency check — that's the strict-semantics path."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_subject(deps)
    asset_id = await _seed_asset(store)

    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=asset_id, reason=""),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(SubjectCannotMountError):
        await mount_subject.bind(deps)(
            MountSubject(subject_id=subject_id, asset_id=asset_id, reason=""),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Subject", subject_id)
    assert version == 2
    assert sum(1 for e in events if e.event_type == "SubjectMounted") == 1


@pytest.mark.unit
def test_wire_subject_includes_mount_subject() -> None:
    deps = _build_deps()
    handlers = wire_subject(deps)
    assert isinstance(handlers, SubjectHandlers)
    assert callable(handlers.mount_subject)
    # register_subject still wired (regression guard for 4a)
    assert callable(handlers.register_subject)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end check that causation_id survives the `with_tracing(bare)` chain in wire.py.

    No idempotency wrap on update-style commands.
    """
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_subject(deps)
    asset_id = await _seed_asset(store)

    handlers = wire_subject(deps)
    await handlers.mount_subject(
        MountSubject(subject_id=subject_id, asset_id=asset_id, reason=""),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Subject", subject_id)
    assert events[1].causation_id == causation


# Suppress pyright's complaint about ConcurrencyError being unused;
# the import surfaces it for any future test that needs to assert
# real concurrency-error propagation against the in-memory store.
_ = ConcurrencyError
