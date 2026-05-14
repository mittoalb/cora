"""Unit tests for the `get_subject` query handler.

Mirrors `test_get_actor_handler.py`. Round-trips through the write
side (register + mount + measure + remove) verify that fold-on-read
correctly reflects every state transition shipped in 4a-d.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.ports import Allow, AuthzResult, Deny
from cora.subject import SubjectHandlers, UnauthorizedError, wire_subject
from cora.subject.aggregates.subject import Subject, SubjectName, SubjectStatus
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
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.subject._asset_helper import seed_active_asset

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000005ab1")
# Multi-step lifecycle round-trips need event ids ready for every
# command consumed in the helper chain (register + mount + measure
# + remove). Excess ids are unused and harmless.
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be1")
_MOUNT_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be2")
_MEASURE_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be3")
_REMOVE_EVENT_ID = UUID("01900000-0000-7000-8000-000000005be4")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(event_store: InMemoryEventStore | None = None) -> Kernel:
    """Thin wrapper preserving this file's ID list."""
    return _build_deps_shared(
        ids=[
            _NEW_ID,
            _REGISTER_EVENT_ID,
            _MOUNT_EVENT_ID,
            _MEASURE_EVENT_ID,
            _REMOVE_EVENT_ID,
        ],
        now=_NOW,
        event_store=event_store,
    )


@pytest.mark.unit
async def test_handler_returns_subject_for_known_id_with_received_status() -> None:
    """Genesis state: just-registered subject is `Received`."""
    deps = _build_deps()
    await register_subject.bind(deps)(
        RegisterSubject(name="Sample-A1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_subject.bind(deps)
    subject = await handler(
        GetSubject(subject_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert subject == Subject(
        id=_NEW_ID, name=SubjectName("Sample-A1"), status=SubjectStatus.RECEIVED
    )


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_id() -> None:
    deps = _build_deps()
    handler = get_subject.bind(deps)
    subject = await handler(
        GetSubject(subject_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert subject is None


@pytest.mark.unit
async def test_handler_reflects_status_after_mount() -> None:
    """Round-trip through the write side: register, mount, then GET."""
    deps = _build_deps()
    await register_subject.bind(deps)(
        RegisterSubject(name="Sample-A1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await seed_active_asset(deps.event_store, now=_NOW, correlation_id=_CORRELATION_ID)
    await mount_subject.bind(deps)(
        MountSubject(subject_id=_NEW_ID, asset_id=asset_id, reason=""),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_subject.bind(deps)
    subject = await handler(
        GetSubject(subject_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert subject is not None
    assert subject.status is SubjectStatus.MOUNTED
    assert subject.name == SubjectName("Sample-A1")


@pytest.mark.unit
async def test_handler_reflects_status_through_full_lifecycle() -> None:
    """Round-trip through register + mount + measure + remove. Pinned
    because fold-on-read must agree with the write-side evolver across
    every transition shipped in 4a-d (regression guard for any future
    evolver edit that diverges from the write path)."""
    deps = _build_deps()
    await register_subject.bind(deps)(
        RegisterSubject(name="Sample-A1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await seed_active_asset(deps.event_store, now=_NOW, correlation_id=_CORRELATION_ID)
    await mount_subject.bind(deps)(
        MountSubject(subject_id=_NEW_ID, asset_id=asset_id, reason=""),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await measure_subject.bind(deps)(
        MeasureSubject(subject_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await remove_subject.bind(deps)(
        RemoveSubject(subject_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_subject.bind(deps)
    subject = await handler(
        GetSubject(subject_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert subject is not None
    assert subject.status is SubjectStatus.REMOVED


class _RecordingAuthorize:
    """Authorize stub that records every call so tests can assert shape."""

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
    """Phase 2 query handlers DO call authorize (with AllowAllAuthorize
    the decision is always Allow, but the call site is in place so the
    eventual TrustAuthorize swap is mechanical per handler)."""
    tracking = _RecordingAuthorize()
    deps = _build_deps_shared(
        ids=[_NEW_ID, _REGISTER_EVENT_ID],
        now=_NOW,
        authorize=tracking,
    )

    handler = get_subject.bind(deps)
    await handler(
        GetSubject(subject_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert tracking.calls == [(_PRINCIPAL_ID, "GetSubject", UUID(int=0))]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps_shared(
        ids=[_NEW_ID, _REGISTER_EVENT_ID],
        now=_NOW,
        authorize=_DenyAllAuthorize(),
    )

    handler = get_subject.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetSubject(subject_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
def test_wire_subject_includes_get_subject() -> None:
    deps = _build_deps()
    handlers = wire_subject(deps)
    assert isinstance(handlers, SubjectHandlers)
    assert callable(handlers.get_subject)
    # earlier-phase handlers still wired (regression guards)
    assert callable(handlers.register_subject)
    assert callable(handlers.mount_subject)
    assert callable(handlers.measure_subject)
    assert callable(handlers.remove_subject)
    assert callable(handlers.return_subject)
    assert callable(handlers.store_subject)
    assert callable(handlers.discard_subject)
