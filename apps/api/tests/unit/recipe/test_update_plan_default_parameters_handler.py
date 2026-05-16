"""Unit tests for the `update_plan_default_parameters` application handler.

Phase 6g-b. Mirrors `test_update_method_parameters_schema_handler.py`
shape but threads the Method-load through the handler under test.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.recipe import RecipeHandlers, UnauthorizedError, wire_recipe
from cora.recipe.aggregates.method.events import (
    MethodDefined,
    MethodParametersSchemaUpdated,
)
from cora.recipe.aggregates.method.events import event_type_name as method_event_type_name
from cora.recipe.aggregates.method.events import to_payload as method_to_payload
from cora.recipe.aggregates.plan import (
    InvalidPlanDefaultParametersError,
    PlanNotFoundError,
)
from cora.recipe.aggregates.plan.events import (
    PlanDefined,
    event_type_name,
    to_payload,
)
from cora.recipe.features import update_plan_default_parameters
from cora.recipe.features.update_plan_default_parameters import (
    UpdatePlanDefaultParameters,
)
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_PLAN_ID = UUID("01900000-0000-7000-8000-00000000cd01")
_METHOD_ID = UUID("01900000-0000-7000-8000-00000000cd02")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-00000000cd03")
_ASSET_ID = UUID("01900000-0000-7000-8000-00000000cd04")
_DEFAULTS_EVENT_ID_1 = UUID("01900000-0000-7000-8000-00000000cd05")
_DEFAULTS_EVENT_ID_2 = UUID("01900000-0000-7000-8000-00000000cd06")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _schema() -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy_kev": {"type": "number", "minimum": 5, "maximum": 50},
            "exposure_ms": {"type": "integer", "minimum": 1},
        },
    }


async def _seed_method(store: InMemoryEventStore, *, schema: dict[str, Any] | None) -> None:
    """Seed a Method with optional parameters_schema directly."""
    define = MethodDefined(
        method_id=_METHOD_ID,
        name="Phase-Contrast Micro-CT",
        needed_capabilities=[],
        occurred_at=_NOW,
    )
    events = [
        to_new_event(
            event_type=method_event_type_name(define),
            payload=method_to_payload(define),
            occurred_at=_NOW,
            event_id=uuid4(),
            command_name="DefineMethod",
            correlation_id=_CORRELATION_ID,
            principal_id=uuid4(),
        )
    ]
    if schema is not None:
        schema_event = MethodParametersSchemaUpdated(
            method_id=_METHOD_ID, parameters_schema=schema, occurred_at=_NOW
        )
        events.append(
            to_new_event(
                event_type=method_event_type_name(schema_event),
                payload=method_to_payload(schema_event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="UpdateMethodParametersSchema",
                correlation_id=_CORRELATION_ID,
                principal_id=uuid4(),
            )
        )
    await store.append(
        stream_type="Method", stream_id=_METHOD_ID, expected_version=0, events=events
    )


async def _seed_plan(store: InMemoryEventStore) -> None:
    """Seed a Plan referencing _METHOD_ID directly."""
    event = PlanDefined(
        plan_id=_PLAN_ID,
        name="32-ID FlyScan",
        practice_id=_PRACTICE_ID,
        asset_ids=[_ASSET_ID],
        method_id=_METHOD_ID,
        method_needed_capabilities_snapshot=[],
        asset_capabilities_snapshot={_ASSET_ID: []},
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Plan",
        stream_id=_PLAN_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="DefinePlan",
                correlation_id=_CORRELATION_ID,
                principal_id=uuid4(),
            )
        ],
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    await _seed_method(store, schema=_schema())
    await _seed_plan(store)
    deps = build_deps(ids=[_DEFAULTS_EVENT_ID_1, _DEFAULTS_EVENT_ID_2], now=_NOW, event_store=store)

    result = await update_plan_default_parameters.bind(deps)(
        UpdatePlanDefaultParameters(
            plan_id=_PLAN_ID, default_parameters_patch={"energy_kev": 12.0}
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_plan_default_parameters_updated_event() -> None:
    store = InMemoryEventStore()
    await _seed_method(store, schema=_schema())
    await _seed_plan(store)
    deps = build_deps(ids=[_DEFAULTS_EVENT_ID_1, _DEFAULTS_EVENT_ID_2], now=_NOW, event_store=store)

    await update_plan_default_parameters.bind(deps)(
        UpdatePlanDefaultParameters(
            plan_id=_PLAN_ID, default_parameters_patch={"energy_kev": 12.0}
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Plan", _PLAN_ID)
    assert version == 2
    assert [e.event_type for e in events] == [
        "PlanDefined",
        "PlanDefaultParametersUpdated",
    ]
    defaults_event = events[1]
    assert defaults_event.event_id == _DEFAULTS_EVENT_ID_1
    assert defaults_event.metadata == {"command": "UpdatePlanDefaultParameters"}
    assert defaults_event.payload["default_parameters"] == {"energy_kev": 12.0}


@pytest.mark.unit
async def test_handler_merges_patch_into_existing_defaults() -> None:
    """RFC 7396 merge: existing keys preserved, patch keys added."""
    store = InMemoryEventStore()
    await _seed_method(store, schema=_schema())
    await _seed_plan(store)
    deps = build_deps(ids=[_DEFAULTS_EVENT_ID_1, _DEFAULTS_EVENT_ID_2], now=_NOW, event_store=store)
    handler = update_plan_default_parameters.bind(deps)

    await handler(
        UpdatePlanDefaultParameters(
            plan_id=_PLAN_ID, default_parameters_patch={"energy_kev": 12.0}
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await handler(
        UpdatePlanDefaultParameters(
            plan_id=_PLAN_ID, default_parameters_patch={"exposure_ms": 250}
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Plan", _PLAN_ID)
    # Second event's payload carries the FULL post-merge dict.
    assert events[2].payload["default_parameters"] == {
        "energy_kev": 12.0,
        "exposure_ms": 250,
    }


@pytest.mark.unit
async def test_handler_no_op_on_unchanged_defaults_does_not_append() -> None:
    store = InMemoryEventStore()
    await _seed_method(store, schema=_schema())
    await _seed_plan(store)
    deps = build_deps(ids=[_DEFAULTS_EVENT_ID_1, _DEFAULTS_EVENT_ID_2], now=_NOW, event_store=store)
    handler = update_plan_default_parameters.bind(deps)

    await handler(
        UpdatePlanDefaultParameters(
            plan_id=_PLAN_ID, default_parameters_patch={"energy_kev": 12.0}
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Re-submit identical patch (merge result == current).
    await handler(
        UpdatePlanDefaultParameters(
            plan_id=_PLAN_ID, default_parameters_patch={"energy_kev": 12.0}
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    _, version = await store.load("Plan", _PLAN_ID)
    assert version == 2  # define + 1 defaults-update; second call no-op


@pytest.mark.unit
async def test_handler_raises_plan_not_found_when_plan_does_not_exist() -> None:
    deps = build_deps(ids=[_DEFAULTS_EVENT_ID_1, _DEFAULTS_EVENT_ID_2], now=_NOW)
    handler = update_plan_default_parameters.bind(deps)
    with pytest.raises(PlanNotFoundError):
        await handler(
            UpdatePlanDefaultParameters(
                plan_id=_PLAN_ID, default_parameters_patch={"energy_kev": 12.0}
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_when_post_merge_violates_schema() -> None:
    store = InMemoryEventStore()
    await _seed_method(store, schema=_schema())
    await _seed_plan(store)
    deps = build_deps(ids=[_DEFAULTS_EVENT_ID_1, _DEFAULTS_EVENT_ID_2], now=_NOW, event_store=store)

    with pytest.raises(InvalidPlanDefaultParametersError):
        await update_plan_default_parameters.bind(deps)(
            UpdatePlanDefaultParameters(
                plan_id=_PLAN_ID, default_parameters_patch={"energy_kev": 1.0}
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_strict_when_method_has_no_schema() -> None:
    """Strict (post-6g audit reversal): Method-without-schema rejects
    non-empty defaults. Pinned at the handler level (the loaded
    Method's parameters_schema is None when no
    MethodParametersSchemaUpdated event has fired)."""
    store = InMemoryEventStore()
    await _seed_method(store, schema=None)
    await _seed_plan(store)
    deps = build_deps(ids=[_DEFAULTS_EVENT_ID_1, _DEFAULTS_EVENT_ID_2], now=_NOW, event_store=store)

    with pytest.raises(InvalidPlanDefaultParametersError):
        await update_plan_default_parameters.bind(deps)(
            UpdatePlanDefaultParameters(
                plan_id=_PLAN_ID,
                default_parameters_patch={"undeclared_key": "anything"},
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Stream untouched: only the seeded PlanDefined event.
    events, version = await store.load("Plan", _PLAN_ID)
    assert version == 1
    assert events[0].event_type == "PlanDefined"


@pytest.mark.unit
async def test_handler_strict_when_method_id_refers_to_missing_stream() -> None:
    """Eventual-consistency edge case: Plan can hold a method_id whose
    stream doesn't exist (Method was never defined or events were
    discarded). Post-audit, handler still loads None from the missing
    stream and the strict validator rejects with the same 'Method
    declares no parameters_schema' message — operator's fix is to
    declare the Method properly OR omit the defaults."""
    store = InMemoryEventStore()
    # NOTE: skip _seed_method — Method stream is empty.
    await _seed_plan(store)
    deps = build_deps(ids=[_DEFAULTS_EVENT_ID_1, _DEFAULTS_EVENT_ID_2], now=_NOW, event_store=store)

    with pytest.raises(InvalidPlanDefaultParametersError):
        await update_plan_default_parameters.bind(deps)(
            UpdatePlanDefaultParameters(
                plan_id=_PLAN_ID, default_parameters_patch={"anything": 42}
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_method(store, schema=_schema())
    await _seed_plan(store)

    deny_deps = build_deps(
        ids=[_DEFAULTS_EVENT_ID_1, _DEFAULTS_EVENT_ID_2], now=_NOW, event_store=store, deny=True
    )
    with pytest.raises(UnauthorizedError) as exc_info:
        await update_plan_default_parameters.bind(deny_deps)(
            UpdatePlanDefaultParameters(
                plan_id=_PLAN_ID, default_parameters_patch={"energy_kev": 12.0}
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    await _seed_method(store, schema=_schema())
    await _seed_plan(store)
    deps = build_deps(ids=[_DEFAULTS_EVENT_ID_1, _DEFAULTS_EVENT_ID_2], now=_NOW, event_store=store)

    await update_plan_default_parameters.bind(deps)(
        UpdatePlanDefaultParameters(
            plan_id=_PLAN_ID, default_parameters_patch={"energy_kev": 12.0}
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Plan", _PLAN_ID)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_recipe_includes_update_plan_default_parameters() -> None:
    deps = build_deps(ids=[_DEFAULTS_EVENT_ID_1, _DEFAULTS_EVENT_ID_2], now=_NOW)
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(handlers.update_plan_default_parameters)
