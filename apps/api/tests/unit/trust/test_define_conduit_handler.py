"""Unit tests for the `define_conduit` application handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.trust import TrustHandlers, UnauthorizedError, wire_trust
from cora.trust.aggregates.conduit import InvalidConduitNameError
from cora.trust.features import define_conduit
from cora.trust.features.define_conduit import DefineConduit
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000000301")
_TRAVERSALS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-000000000311")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-0000000003e1")
_LOGBOOK_OPENED_EVENT_ID = UUID("01900000-0000-7000-8000-0000000003e2")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_SOURCE_ZONE = UUID("01900000-0000-7000-8000-00000000aaaa")
_TARGET_ZONE = UUID("01900000-0000-7000-8000-00000000bbbb")


def _command(name: str = "Detector-to-Storage") -> DefineConduit:
    return DefineConduit(
        name=name,
        source_zone_id=_SOURCE_ZONE,
        target_zone_id=_TARGET_ZONE,
    )


@pytest.mark.unit
async def test_handler_returns_generated_conduit_id() -> None:
    deps = build_deps(
        ids=[_NEW_ID, _TRAVERSALS_LOGBOOK_ID, _DEFINED_EVENT_ID, _LOGBOOK_OPENED_EVENT_ID], now=_NOW
    )
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
    deps = build_deps(
        ids=[_NEW_ID, _TRAVERSALS_LOGBOOK_ID, _DEFINED_EVENT_ID, _LOGBOOK_OPENED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    handler = define_conduit.bind(deps)

    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Conduit", _NEW_ID)

    # (genesis) + ConduitLogbookOpened (auto-opens traversals channel).
    assert version == 2
    assert [e.event_type for e in events] == ["ConduitDefined", "ConduitLogbookOpened"]
    defined = events[0]
    assert defined.schema_version == 1
    assert defined.payload == {
        "conduit_id": str(_NEW_ID),
        "name": "Detector-to-Storage",
        "source_zone_id": str(_SOURCE_ZONE),
        "target_zone_id": str(_TARGET_ZONE),
        "occurred_at": _NOW.isoformat(),
    }
    assert defined.correlation_id == _CORRELATION_ID
    assert defined.causation_id is None
    assert defined.event_id == _DEFINED_EVENT_ID
    assert defined.metadata == {"command": "DefineConduit"}
    assert defined.occurred_at == _NOW

    logbook_opened = events[1]
    assert logbook_opened.event_id == _LOGBOOK_OPENED_EVENT_ID
    assert logbook_opened.payload["conduit_id"] == str(_NEW_ID)
    assert logbook_opened.payload["logbook_id"] == str(_TRAVERSALS_LOGBOOK_ID)
    assert logbook_opened.payload["kind"] == "traversals"
    assert logbook_opened.metadata == {"command": "DefineConduit"}
    assert logbook_opened.correlation_id == _CORRELATION_ID
    assert logbook_opened.causation_id is None
    # Schema is captured verbatim in the payload so the audit trail
    # records the column shape at the moment of opening.
    assert "fields" in logbook_opened.payload["schema"]
    assert set(logbook_opened.payload["schema"]["fields"]) == {
        "actor_id",
        "command_name",
        "decision",
        "reason",
    }


@pytest.mark.unit
async def test_handler_trims_conduit_name_via_value_object() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_NEW_ID, _TRAVERSALS_LOGBOOK_ID, _DEFINED_EVENT_ID, _LOGBOOK_OPENED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
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
    deps = build_deps(
        ids=[_NEW_ID, _TRAVERSALS_LOGBOOK_ID, _DEFINED_EVENT_ID, _LOGBOOK_OPENED_EVENT_ID],
        now=_NOW,
        deny=True,
    )
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
    deps = build_deps(
        ids=[_NEW_ID, _TRAVERSALS_LOGBOOK_ID, _DEFINED_EVENT_ID, _LOGBOOK_OPENED_EVENT_ID],
        now=_NOW,
        event_store=store,
        deny=True,
    )
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
    deps = build_deps(
        ids=[_NEW_ID, _TRAVERSALS_LOGBOOK_ID, _DEFINED_EVENT_ID, _LOGBOOK_OPENED_EVENT_ID], now=_NOW
    )
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
    deps = build_deps(
        ids=[_NEW_ID, _TRAVERSALS_LOGBOOK_ID, _DEFINED_EVENT_ID, _LOGBOOK_OPENED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
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
    deps = build_deps(
        ids=[_NEW_ID, _TRAVERSALS_LOGBOOK_ID, _DEFINED_EVENT_ID, _LOGBOOK_OPENED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    handler = define_conduit.bind(deps)

    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Conduit", _NEW_ID)
    assert events[0].causation_id == causation

    # (ConduitDefined + ConduitLogbookOpened share the command's
    # causation chain).
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_trust_returns_handlers_bundle_with_define_conduit() -> None:
    deps = build_deps(
        ids=[_NEW_ID, _TRAVERSALS_LOGBOOK_ID, _DEFINED_EVENT_ID, _LOGBOOK_OPENED_EVENT_ID], now=_NOW
    )
    handlers = wire_trust(deps)
    assert isinstance(handlers, TrustHandlers)
    assert callable(handlers.define_conduit)
    # define_zone is still wired alongside (regression guard for the prior slice)
    assert callable(handlers.define_zone)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end check that causation_id survives the
    `with_tracing(with_idempotency(bare))` chain in wire.py for the
    second slice on this BC."""
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_NEW_ID, _TRAVERSALS_LOGBOOK_ID, _DEFINED_EVENT_ID, _LOGBOOK_OPENED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    handlers = wire_trust(deps)

    await handlers.define_conduit(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Conduit", _NEW_ID)
    assert events[0].causation_id == causation
