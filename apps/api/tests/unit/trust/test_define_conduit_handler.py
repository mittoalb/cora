"""Unit tests for the `define_conduit` application handler."""

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
from cora.trust.aggregates.conduit import InvalidConduitNameError
from cora.trust.features import define_conduit
from cora.trust.features.define_conduit import DefineConduit

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000000301")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000003e1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_SOURCE_ZONE = UUID("01900000-0000-7000-8000-00000000aaaa")
_TARGET_ZONE = UUID("01900000-0000-7000-8000-00000000bbbb")


class DenyAllAuthorize:
    """Authorize stub that denies every command."""

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
        id_generator=FixedIdGenerator([_NEW_ID, _EVENT_ID]),
        authorize=DenyAllAuthorize() if deny else AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


def _command(name: str = "Detector-to-Storage") -> DefineConduit:
    return DefineConduit(
        name=name,
        source_zone_id=_SOURCE_ZONE,
        target_zone_id=_TARGET_ZONE,
    )


@pytest.mark.unit
async def test_handler_returns_generated_conduit_id() -> None:
    deps = _build_deps()
    handler = define_conduit.bind(deps)

    result = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_conduit_defined_event_to_store() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_conduit.bind(deps)

    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Conduit", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "ConduitDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "conduit_id": str(_NEW_ID),
        "name": "Detector-to-Storage",
        "source_zone_id": str(_SOURCE_ZONE),
        "target_zone_id": str(_TARGET_ZONE),
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefineConduit"}
    assert stored.occurred_at == _NOW


@pytest.mark.unit
async def test_handler_trims_conduit_name_via_value_object() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_conduit.bind(deps)

    await handler(
        _command(name="  Detector-to-Storage  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Conduit", _NEW_ID)
    assert events[0].payload["name"] == "Detector-to-Storage"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)
    handler = define_conduit.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = define_conduit.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Conduit", _NEW_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_propagates_invalid_conduit_name_error() -> None:
    deps = _build_deps()
    handler = define_conduit.bind(deps)

    with pytest.raises(InvalidConduitNameError):
        await handler(
            _command(name="   "),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_does_not_append_when_decider_rejects() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_conduit.bind(deps)

    with pytest.raises(InvalidConduitNameError):
        await handler(
            _command(name=""),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Conduit", _NEW_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_conduit.bind(deps)

    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Conduit", _NEW_ID)
    assert events[0].causation_id == causation


@pytest.mark.unit
def test_wire_trust_returns_handlers_bundle_with_define_conduit() -> None:
    deps = _build_deps()
    handlers = wire_trust(deps)
    assert isinstance(handlers, TrustHandlers)
    assert callable(handlers.define_conduit)
    # define_zone is still wired alongside (regression guard for Phase 3a slice)
    assert callable(handlers.define_zone)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end check that causation_id survives the
    `with_tracing(with_idempotency(bare))` chain in wire.py for the
    second slice on this BC."""
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handlers = wire_trust(deps)

    await handlers.define_conduit(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Conduit", _NEW_ID)
    assert events[0].causation_id == causation
