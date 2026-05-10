"""Unit tests for the `define_zone` application handler."""

from datetime import UTC, datetime
from uuid import UUID

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
from cora.trust import TrustHandlers, UnauthorizedError, wire_trust
from cora.trust.aggregates.zone import InvalidZoneNameError
from cora.trust.features import define_zone
from cora.trust.features.define_zone import DefineZone

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000000201")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000002e1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


class DenyAllAuthorize:
    """Authorize stub that denies every command."""

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
) -> SharedDeps:
    settings = Settings(app_env="test")  # type: ignore[call-arg]
    return SharedDeps(
        settings=settings,
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_NEW_ID, _EVENT_ID]),
        authorize=DenyAllAuthorize() if deny else AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


@pytest.mark.unit
async def test_handler_returns_generated_zone_id() -> None:
    deps = _build_deps()
    handler = define_zone.bind(deps)

    result = await handler(
        DefineZone(name="Detector"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_zone_defined_event_to_store() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_zone.bind(deps)

    await handler(
        DefineZone(name="Detector"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Zone", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "ZoneDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "zone_id": str(_NEW_ID),
        "name": "Detector",
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefineZone"}
    assert stored.occurred_at == _NOW


@pytest.mark.unit
async def test_handler_trims_zone_name_via_value_object() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_zone.bind(deps)

    await handler(
        DefineZone(name="  Detector  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Zone", _NEW_ID)
    assert events[0].payload["name"] == "Detector"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)
    handler = define_zone.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            DefineZone(name="Detector"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = define_zone.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            DefineZone(name="Detector"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Zone", _NEW_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_propagates_invalid_zone_name_error() -> None:
    deps = _build_deps()
    handler = define_zone.bind(deps)

    with pytest.raises(InvalidZoneNameError):
        await handler(
            DefineZone(name="   "),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_does_not_append_when_decider_rejects() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_zone.bind(deps)

    with pytest.raises(InvalidZoneNameError):
        await handler(
            DefineZone(name=""),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Zone", _NEW_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_zone.bind(deps)

    await handler(
        DefineZone(name="Detector"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Zone", _NEW_ID)
    assert events[0].causation_id == causation


@pytest.mark.unit
def test_wire_trust_returns_handlers_bundle() -> None:
    deps = _build_deps()
    handlers = wire_trust(deps)
    assert isinstance(handlers, TrustHandlers)
    assert callable(handlers.define_zone)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end check that causation_id survives the
    `with_tracing(with_idempotency(bare))` composition chain in wire.py.
    """
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handlers = wire_trust(deps)

    await handlers.define_zone(
        DefineZone(name="Detector"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Zone", _NEW_ID)
    assert events[0].causation_id == causation
