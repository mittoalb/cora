"""Unit tests for the `get_family` query handler.

Mirrors `test_get_subject_handler.py` / `test_get_actor_handler.py`.
Round-trips through the write side (define → get) verify that
fold-on-read correctly returns the registered Family.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.family import (
    Family,
    FamilyName,
    FamilyStatus,
)
from cora.equipment.features import define_family, get_family
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.get_family import GetFamily
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.ports import Allow, AuthzResult
from tests.unit._helpers import DenyAllAuthorize as _DenyAllAuthorize
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000006ab1")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000006be1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(event_store: InMemoryEventStore | None = None) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    return _build_deps_shared(
        ids=[_NEW_ID, _EVENT_ID],
        now=_NOW,
        event_store=event_store,
    )


@pytest.mark.unit
async def test_handler_returns_capability_for_known_id() -> None:
    """Round-trip: define + get."""
    deps = _build_deps()
    await define_family.bind(deps)(
        DefineFamily(name="Tomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_family.bind(deps)
    capability = await handler(
        GetFamily(family_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert capability == Family(
        id=_NEW_ID,
        name=FamilyName("Tomography"),
        status=FamilyStatus.DEFINED,
    )


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_id() -> None:
    deps = _build_deps()
    handler = get_family.bind(deps)
    capability = await handler(
        GetFamily(family_id=uuid4()),
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


@pytest.mark.unit
async def test_handler_authorizes_with_query_name_and_default_conduit() -> None:
    """Phase 2 query handlers DO call authorize. Pinned because the
    eventual TrustAuthorize swap is mechanical per handler — the call
    site has to exist."""
    tracking = _RecordingAuthorize()
    deps = _build_deps_shared(
        ids=[_NEW_ID, _EVENT_ID],
        now=_NOW,
        authorize=tracking,
    )

    handler = get_family.bind(deps)
    await handler(
        GetFamily(family_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert tracking.calls == [(_PRINCIPAL_ID, "GetFamily", UUID(int=0))]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps_shared(
        ids=[_NEW_ID, _EVENT_ID],
        now=_NOW,
        authorize=_DenyAllAuthorize(),
    )

    handler = get_family.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetFamily(family_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
def test_wire_equipment_includes_get_family() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.get_family)
    assert callable(handlers.define_family)
