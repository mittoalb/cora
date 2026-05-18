"""Unit tests for the `define_method` application handler."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.recipe import RecipeHandlers, UnauthorizedError, wire_recipe
from cora.recipe.aggregates.capability import (
    CapabilityCode,
    CapabilityName,
    CapabilityNotFoundError,
    ExecutorShape,
    RecipeCapabilityDefined,
)
from cora.recipe.aggregates.capability import (
    event_type_name as capability_event_type_name,
)
from cora.recipe.aggregates.capability import (
    to_payload as capability_to_payload,
)
from cora.recipe.aggregates.method import InvalidMethodNameError
from cora.recipe.features import define_method
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method.decider import (
    MethodCapabilityExecutorMismatchError,
)
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000ab01")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ab02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAP1 = UUID("01900000-0000-7000-8000-000000000111")
_CAP2 = UUID("01900000-0000-7000-8000-000000000222")


async def _seed_capability(
    store: InMemoryEventStore,
    capability_id: UUID,
    *,
    shapes: frozenset[ExecutorShape] = frozenset({ExecutorShape.METHOD}),
) -> None:
    """Seed a Capability stream so load_capability returns a real Capability."""
    event = RecipeCapabilityDefined(
        capability_id=capability_id,
        code=CapabilityCode("cora.capability.x").value,
        name=CapabilityName("X").value,
        required_affordances=frozenset(),
        executor_shapes=shapes,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=capability_event_type_name(event),
        payload=capability_to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="DefineCapability",
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="Capability",
        stream_id=capability_id,
        expected_version=0,
        events=[new_event],
    )


@pytest.mark.unit
async def test_handler_returns_generated_method_id() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handler = define_method.bind(deps)

    result = await handler(
        DefineMethod(name="XRF Mapping", needed_families=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_method_defined_event_to_store() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(name="XRF Fly Mapping", needed_families=frozenset({_CAP1, _CAP2})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Method", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "MethodDefined"
    assert stored.schema_version == 1
    # Payload's needed_families is sorted by string form
    # (deterministic). Compare exact bytes to lock the contract.
    assert stored.payload == {
        "method_id": str(_NEW_ID),
        "name": "XRF Fly Mapping",
        "needed_families": sorted([str(_CAP1), str(_CAP2)]),
        # Phase 10b additive: empty list when MethodDefined has no
        # needed_supplies. Pinned by test_method_needed_supplies.py.
        "needed_supplies": [],
        # Phase 6l-additive: None when DefineMethod omits capability_id.
        # 6l-strict will require capability_id at the command level.
        "capability_id": None,
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefineMethod"}
    assert stored.occurred_at == _NOW


@pytest.mark.unit
async def test_handler_handles_empty_needed_families() -> None:
    """Procedural Method (no equipment requirement) lands as
    payload `needed_families = []`."""
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(name="Sample Cleaning", needed_families=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].payload["needed_families"] == []


@pytest.mark.unit
async def test_handler_trims_method_name_via_value_object() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(name="  XRF Mapping  ", needed_families=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].payload["name"] == "XRF Mapping"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, deny=True)
    handler = define_method.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            DefineMethod(name="X", needed_families=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = define_method.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            DefineMethod(name="X", needed_families=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Method", _NEW_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_propagates_invalid_method_name_error() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handler = define_method.bind(deps)

    with pytest.raises(InvalidMethodNameError):
        await handler(
            DefineMethod(name="   ", needed_families=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_emits_byte_identical_payload_for_same_capability_id() -> None:
    """Phase 6l-additive determinism pin (gate-review P0): two
    DefineMethod calls with the same logical inputs — INCLUDING the
    new `capability_id` key — must produce byte-identical persisted
    `MethodDefined.payload` dicts. Required for idempotency-key
    hashing to stay stable across the additive payload shape change
    (see `with_idempotency` SHA256 over normalized request body)."""
    capability_id = UUID("01900000-0000-7000-8000-00000000c0d1")
    needed_families = frozenset({_CAP1, _CAP2})

    # Run 1
    store_a = InMemoryEventStore()
    await _seed_capability(store_a, capability_id)
    deps_a = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store_a)
    await define_method.bind(deps_a)(
        DefineMethod(
            name="XRF Fly Mapping",
            needed_families=needed_families,
            capability_id=capability_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events_a, _ = await store_a.load("Method", _NEW_ID)

    # Run 2 (fresh store + deps)
    store_b = InMemoryEventStore()
    await _seed_capability(store_b, capability_id)
    deps_b = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store_b)
    await define_method.bind(deps_b)(
        DefineMethod(
            name="XRF Fly Mapping",
            needed_families=needed_families,
            capability_id=capability_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events_b, _ = await store_b.load("Method", _NEW_ID)

    assert events_a[0].payload == events_b[0].payload
    assert events_a[0].payload["capability_id"] == str(capability_id)


@pytest.mark.unit
async def test_handler_loads_and_validates_bound_capability_when_set() -> None:
    """Phase 6l-additive happy path through the handler: when
    DefineMethod.capability_id is set, the handler loads the
    Capability stream via `load_capability`, passes the loaded state
    to the decider, and the persisted MethodDefined payload carries
    the bound capability_id."""
    capability_id = UUID("01900000-0000-7000-8000-00000000c001")
    store = InMemoryEventStore()
    await _seed_capability(store, capability_id)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(name="X", capability_id=capability_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].payload["capability_id"] == str(capability_id)


@pytest.mark.unit
async def test_handler_raises_capability_not_found_when_stream_missing() -> None:
    """Phase 6l-additive: capability_id set on the command but no
    Capability stream exists for it. load_capability returns None;
    the decider raises CapabilityNotFoundError (mapped to 404 at the
    HTTP boundary)."""
    bogus = UUID("01900000-0000-7000-8000-deadbeefcafe")
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_method.bind(deps)

    with pytest.raises(CapabilityNotFoundError):
        await handler(
            DefineMethod(name="X", capability_id=bogus),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    method_events, version = await store.load("Method", _NEW_ID)
    assert method_events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_raises_executor_mismatch_when_capability_excludes_method() -> None:
    """Phase 6l-additive: capability_id binds to a Procedure-only
    Capability. Handler propagates MethodCapabilityExecutorMismatchError
    (mapped to 409). Critical: no Method event should be persisted
    when the cross-BC guard fires."""
    capability_id = UUID("01900000-0000-7000-8000-00000000c002")
    store = InMemoryEventStore()
    await _seed_capability(store, capability_id, shapes=frozenset({ExecutorShape.PROCEDURE}))
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_method.bind(deps)

    with pytest.raises(MethodCapabilityExecutorMismatchError) as exc_info:
        await handler(
            DefineMethod(name="X", capability_id=capability_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.capability_id == capability_id

    method_events, version = await store.load("Method", _NEW_ID)
    assert method_events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_skips_capability_load_when_command_omits_capability_id() -> None:
    """Phase 6l-additive: when capability_id is None on the command,
    the handler does NOT call load_capability — the legacy pre-6l
    define_method path stays cost-free. Pinned via a sentinel event
    store that raises if load is invoked on the Capability stream."""

    class _CapabilityLoadGuard(InMemoryEventStore):
        async def load(self, stream_type: str, stream_id: UUID):  # type: ignore[override]
            assert stream_type != "Capability", (
                "load_capability should not run when DefineMethod.capability_id is None"
            )
            return await super().load(stream_type, stream_id)

    store = _CapabilityLoadGuard()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(name="X"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].payload["capability_id"] is None


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(name="X", needed_families=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].causation_id == causation


@pytest.mark.unit
def test_wire_recipe_returns_handlers_bundle() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(handlers.define_method)
    assert callable(handlers.get_method)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end: causation_id survives `with_tracing(with_idempotency(bare))`."""
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handlers = wire_recipe(deps)

    await handlers.define_method(
        DefineMethod(name="X", needed_families=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].causation_id == causation
