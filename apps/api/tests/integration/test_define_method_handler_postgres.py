"""End-to-end integration test: define_method handler against real Postgres.

Pinned: needed_families round-trips through jsonb as a sorted
list of UUID strings. The frozenset[UUID] domain shape converts
to list[UUID] at the events layer (see PolicyDefined precedent in
Trust 3c).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.recipe.aggregates.capability import (
    CapabilityCode,
    CapabilityName,
    ExecutorShape,
    RecipeCapabilityDefined,
)
from cora.recipe.aggregates.capability import (
    event_type_name as capability_event_type_name,
)
from cora.recipe.aggregates.capability import (
    to_payload as capability_to_payload,
)
from cora.recipe.features import define_method
from cora.recipe.features.define_method import DefineMethod
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_define_method_persists_event_to_postgres_with_capabilities(
    db_pool: asyncpg.Pool,
) -> None:
    method_id = UUID("01900000-0000-7000-8000-00000056ed01")
    event_id = UUID("01900000-0000-7000-8000-00000056ed0e")
    cap1 = UUID("01900000-0000-7000-8000-000000000111")
    cap2 = UUID("01900000-0000-7000-8000-000000000222")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[method_id, event_id])

    returned_id = await define_method.bind(deps)(
        DefineMethod(
            name="XRF Fly Mapping",
            needed_families=frozenset({cap2, cap1}),  # unsorted input
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == method_id

    events, version = await deps.event_store.load("Method", method_id)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "MethodDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "method_id": str(method_id),
        "name": "XRF Fly Mapping",
        # Sorted by UUID string form (deterministic).
        "needed_families": sorted([str(cap1), str(cap2)]),
        # Phase 10b additive: empty list when MethodDefined has no
        # needed_supplies. Pinned by tests/unit/recipe/test_method_needed_supplies.py.
        "needed_supplies": [],
        # Phase 6l-additive: None when DefineMethod omits capability_id.
        "capability_id": None,
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == event_id
    assert stored.metadata == {"command": "DefineMethod"}
    assert stored.occurred_at == _NOW


@pytest.mark.integration
async def test_define_method_persists_procedural_method_with_empty_capabilities(
    db_pool: asyncpg.Pool,
) -> None:
    """Procedural Method (no equipment requirement) round-trips
    through jsonb with `needed_families = []`."""
    method_id = UUID("01900000-0000-7000-8000-00000056ee01")
    event_id = UUID("01900000-0000-7000-8000-00000056ee0e")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[method_id, event_id])

    await define_method.bind(deps)(
        DefineMethod(name="Sample Cleaning", needed_families=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await deps.event_store.load("Method", method_id)
    assert events[0].payload["needed_families"] == []


@pytest.mark.integration
async def test_define_method_persists_bound_capability_id_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Phase 6l-additive PG round-trip (gate-review P1): when
    `DefineMethod.capability_id` is set, the handler loads the
    bound Capability from PG, validates `ExecutorShape.METHOD` is
    declared, and persists the resolved capability_id into the
    MethodDefined payload as a UUID string. Pinned because the
    cross-BC capability load uses jsonb-serialized executor_shapes
    via `to_payload` + the round-trip through Postgres."""
    method_id = UUID("01900000-0000-7000-8000-00000056ef01")
    event_id = UUID("01900000-0000-7000-8000-00000056ef0e")
    capability_id = UUID("01900000-0000-7000-8000-00000000c0d2")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[method_id, event_id])

    # Seed a Capability stream directly in PG so load_capability can
    # find it. Mirrors the pattern unit tests use against InMemoryEventStore.
    cap_event = RecipeCapabilityDefined(
        capability_id=capability_id,
        code=CapabilityCode("cora.capability.x").value,
        name=CapabilityName("X").value,
        required_affordances=frozenset(),
        executor_shapes=frozenset({ExecutorShape.METHOD}),
        occurred_at=_NOW,
    )
    await deps.event_store.append(
        stream_type="Capability",
        stream_id=capability_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=capability_event_type_name(cap_event),
                payload=capability_to_payload(cap_event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="DefineCapability",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )

    await define_method.bind(deps)(
        DefineMethod(name="X", capability_id=capability_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await deps.event_store.load("Method", method_id)
    assert events[0].payload["capability_id"] == str(capability_id)
