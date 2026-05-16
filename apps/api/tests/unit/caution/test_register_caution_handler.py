"""Application-handler tests for `register_caution` slice."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionCategory,
    CautionSeverity,
    ProcedureTarget,
)
from cora.caution.errors import UnauthorizedError
from cora.caution.features import register_caution
from cora.caution.features.register_caution import RegisterCaution
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000f001")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000f002")
_ASSET_ID = UUID("01900000-0000-7000-8000-00000000f003")
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-00000000f004")
_AUTHOR_ID = UUID("01900000-0000-7000-8000-00000000f005")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEW_ID, _EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


def _command(**overrides: object) -> RegisterCaution:
    base: dict[str, object] = {
        "target": AssetTarget(asset_id=_ASSET_ID),
        "category": CautionCategory.Wear,
        "severity": CautionSeverity.Caution,
        "text": "hexapod stalls below 0.5 mm/s",
        "workaround": "run at 0.6 mm/s",
        "author_actor_id": _AUTHOR_ID,
    }
    base.update(overrides)
    return RegisterCaution(**base)  # type: ignore[arg-type]


@pytest.mark.unit
async def test_handler_returns_generated_caution_id() -> None:
    deps = _build_deps()
    handler = register_caution.bind(deps)
    result = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_caution_registered_event_to_store() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_caution.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Caution", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "CautionRegistered"
    assert stored.payload["caution_id"] == str(_NEW_ID)
    assert stored.payload["target"] == {"kind": "Asset", "id": str(_ASSET_ID)}
    assert stored.payload["category"] == "Wear"
    assert stored.payload["severity"] == "Caution"
    assert stored.payload["text"] == "hexapod stalls below 0.5 mm/s"
    assert stored.payload["workaround"] == "run at 0.6 mm/s"
    assert stored.payload["author_actor_id"] == str(_AUTHOR_ID)
    assert stored.payload["propagate_to_children"] is False
    assert stored.payload["parent_caution_id"] is None
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.event_id == _EVENT_ID
    assert stored.principal_id == _PRINCIPAL_ID
    assert stored.metadata == {"command": "RegisterCaution"}


@pytest.mark.unit
async def test_handler_serializes_procedure_target() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_caution.bind(deps)
    await handler(
        _command(target=ProcedureTarget(procedure_id=_PROCEDURE_ID)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Caution", _NEW_ID)
    assert events[0].payload["target"] == {"kind": "Procedure", "id": str(_PROCEDURE_ID)}


@pytest.mark.unit
async def test_handler_serializes_tags_sorted() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_caution.bind(deps)
    await handler(
        _command(tags=frozenset({"zeta", "alpha", "mu"})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Caution", _NEW_ID)
    assert events[0].payload["tags"] == ["alpha", "mu", "zeta"]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)
    handler = register_caution.bind(deps)
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
    handler = register_caution.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Caution", _NEW_ID)
    assert version == 0
    assert events == []


@pytest.mark.unit
async def test_handler_records_causation_id_when_provided() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_caution.bind(deps)
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Caution", _NEW_ID)
    assert events[0].causation_id == causation
