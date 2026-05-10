"""Unit tests for the `discard_subject` application handler.

Mirrors `test_return_subject_handler.py` for the Discarded terminal slice.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.config import Settings
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    AuthzResult,
    Deny,
    FixedIdGenerator,
    FrozenClock,
)
from cora.subject import SubjectHandlers, UnauthorizedError, wire_subject
from cora.subject.aggregates.subject import (
    SubjectCannotDiscardError,
    SubjectNotFoundError,
    SubjectStatus,
)
from cora.subject.features import (
    discard_subject,
    mount_subject,
    register_subject,
    remove_subject,
)
from cora.subject.features.discard_subject import DiscardSubject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from cora.subject.features.remove_subject import RemoveSubject

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000005ab1")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be1")
_MOUNT_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be2")
_REMOVE_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be3")
_DISCARD_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be4")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


class DenyAllAuthorize:
    async def __call__(
        self,
        principal_id: UUID,
        command_name: str,
        conduit: str,
    ) -> AuthzResult:
        _ = (principal_id, command_name, conduit)
        return Deny(reason="denied for test")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> SharedDeps:
    settings = Settings(app_env="test")  # type: ignore[call-arg]
    return SharedDeps(
        settings=settings,
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator(
            [
                _NEW_ID,
                _REGISTER_EVENT_ID,
                _MOUNT_EVENT_ID,
                _REMOVE_EVENT_ID,
                _DISCARD_EVENT_ID,
            ],
        ),
        authorize=DenyAllAuthorize() if deny else AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


async def _register_mount_remove(deps: SharedDeps) -> UUID:
    """Helper: register + mount + remove a subject and return its id."""
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
    return subject_id


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_mount_remove(deps)

    result = await discard_subject.bind(deps)(
        DiscardSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_subject_discarded_event() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_mount_remove(deps)

    await discard_subject.bind(deps)(
        DiscardSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Subject", subject_id)
    assert version == 4
    discarded = events[3]
    assert discarded.event_type == "SubjectDiscarded"
    assert discarded.payload == {
        "subject_id": str(subject_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert discarded.event_id == _DISCARD_EVENT_ID
    assert discarded.metadata == {"command": "DiscardSubject"}
    assert discarded.causation_id is None


@pytest.mark.unit
async def test_handler_raises_subject_not_found_when_subject_does_not_exist() -> None:
    deps = _build_deps()
    handler = discard_subject.bind(deps)

    with pytest.raises(SubjectNotFoundError):
        await handler(
            DiscardSubject(subject_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_discard_when_subject_not_yet_removed() -> None:
    """Strict semantics: discarding a Mounted (not yet Removed) subject raises."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
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

    handler = discard_subject.bind(deps)
    with pytest.raises(SubjectCannotDiscardError) as exc_info:
        await handler(
            DiscardSubject(subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.subject_id == subject_id
    assert exc_info.value.current_status is SubjectStatus.MOUNTED


@pytest.mark.unit
async def test_handler_raises_cannot_discard_when_subject_already_discarded() -> None:
    """Strict semantics: re-discarding raises."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_mount_remove(deps)

    handler = discard_subject.bind(deps)
    await handler(
        DiscardSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(SubjectCannotDiscardError) as exc_info:
        await handler(
            DiscardSubject(subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.subject_id == subject_id
    assert exc_info.value.current_status is SubjectStatus.DISCARDED


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_mount_remove(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    handler = discard_subject.bind(deny_deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            DiscardSubject(subject_id=subject_id),
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
        await discard_subject.bind(deny_deps)(
            DiscardSubject(subject_id=subject_id),
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

    await discard_subject.bind(deps)(
        DiscardSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Subject", subject_id)
    assert events[3].causation_id == causation


@pytest.mark.unit
def test_wire_subject_includes_discard_subject() -> None:
    deps = _build_deps()
    handlers = wire_subject(deps)
    assert isinstance(handlers, SubjectHandlers)
    assert callable(handlers.discard_subject)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    subject_id = await _register_mount_remove(deps)

    handlers = wire_subject(deps)
    await handlers.discard_subject(
        DiscardSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Subject", subject_id)
    assert events[3].causation_id == causation
