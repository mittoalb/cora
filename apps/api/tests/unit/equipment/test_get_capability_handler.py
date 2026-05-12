"""Unit tests for the `get_capability` query handler.

Mirrors `test_get_subject_handler.py` / `test_get_actor_handler.py`.
Round-trips through the write side (define → get) verify that
fold-on-read correctly returns the registered Capability.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.capability import (
    Capability,
    CapabilityName,
    CapabilityStatus,
)
from cora.equipment.features import define_capability, get_capability
from cora.equipment.features.define_capability import DefineCapability
from cora.equipment.features.get_capability import GetCapability
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
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

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000006ab1")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000006be1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(event_store: InMemoryEventStore | None = None) -> Kernel:
    settings = Settings(app_env="test")  # type: ignore[call-arg]
    return Kernel(
        settings=settings,
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_NEW_ID, _EVENT_ID]),
        authorize=AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


@pytest.mark.unit
async def test_handler_returns_capability_for_known_id() -> None:
    """Round-trip: define + get."""
    deps = _build_deps()
    await define_capability.bind(deps)(
        DefineCapability(name="Tomography"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_capability.bind(deps)
    capability = await handler(
        GetCapability(capability_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert capability == Capability(
        id=_NEW_ID,
        name=CapabilityName("Tomography"),
        status=CapabilityStatus.DEFINED,
    )


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_id() -> None:
    deps = _build_deps()
    handler = get_capability.bind(deps)
    capability = await handler(
        GetCapability(capability_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert capability is None


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
    """Phase 2 query handlers DO call authorize. Pinned because the
    eventual TrustAuthorize swap is mechanical per handler — the call
    site has to exist."""
    tracking = _RecordingAuthorize()
    deps = Kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_NEW_ID, _EVENT_ID]),
        authorize=tracking,
        event_store=InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )

    handler = get_capability.bind(deps)
    await handler(
        GetCapability(capability_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert tracking.calls == [(_PRINCIPAL_ID, "GetCapability", UUID(int=0))]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = Kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_NEW_ID, _EVENT_ID]),
        authorize=_DenyAllAuthorize(),
        event_store=InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )

    handler = get_capability.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetCapability(capability_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
def test_wire_equipment_includes_get_capability() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.get_capability)
    assert callable(handlers.define_capability)
