"""Unit tests for the `adjust_run` application handler.

Longhand cross-aggregate handler: loads Run + Plan + Practice + Method
before reaching the pure decider. Mirrors `start_run`'s handler test
shape; seeds the upstream chain via direct event-store appends.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.recipe.aggregates.method import MethodNotFoundError
from cora.recipe.aggregates.method.events import (
    MethodDefined,
    MethodParametersSchemaUpdated,
)
from cora.recipe.aggregates.method.events import (
    event_type_name as method_event_type_name,
)
from cora.recipe.aggregates.method.events import to_payload as method_to_payload
from cora.recipe.aggregates.plan import PlanNotFoundError
from cora.recipe.aggregates.plan.events import PlanDefined
from cora.recipe.aggregates.plan.events import (
    event_type_name as plan_event_type_name,
)
from cora.recipe.aggregates.plan.events import to_payload as plan_to_payload
from cora.recipe.aggregates.practice import PracticeNotFoundError
from cora.recipe.aggregates.practice.events import PracticeDefined
from cora.recipe.aggregates.practice.events import (
    event_type_name as practice_event_type_name,
)
from cora.recipe.aggregates.practice.events import (
    to_payload as practice_to_payload,
)
from cora.run import RunHandlers, UnauthorizedError, wire_run
from cora.run.aggregates.run import RunNotFoundError
from cora.run.aggregates.run.events import (
    RunStarted,
    event_type_name,
    to_payload,
)
from cora.run.features import adjust_run
from cora.run.features.adjust_run import AdjustRun
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_RUN_ID = UUID("01900000-0000-7000-8000-000000006a01")
_ADJUSTED_EVENT_ID = UUID("01900000-0000-7000-8000-000000006a02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DRAFT = "https://json-schema.org/draft/2020-12/schema"


async def _append(
    store: InMemoryEventStore,
    *,
    stream_type: str,
    stream_id: UUID,
    expected_version: int,
    event_type: str,
    payload: dict[str, object],
    command_name: str,
) -> None:
    new_event = to_new_event(
        event_type=event_type,
        payload=payload,
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name=command_name,
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type=stream_type,
        stream_id=stream_id,
        expected_version=expected_version,
        events=[new_event],
    )


async def _seed_method(
    store: InMemoryEventStore,
    method_id: UUID,
    *,
    parameters_schema: dict[str, Any] | None = None,
) -> None:
    """Seed a Method (and optionally a schema-update event)."""
    define_event = MethodDefined(
        method_id=method_id,
        name="Test Method",
        needed_family_ids=(),
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Method",
        stream_id=method_id,
        expected_version=0,
        event_type=method_event_type_name(define_event),
        payload=method_to_payload(define_event),
        command_name="DefineMethod",
    )
    if parameters_schema is not None:
        schema_event = MethodParametersSchemaUpdated(
            method_id=method_id,
            parameters_schema=parameters_schema,
            occurred_at=_NOW,
        )
        await _append(
            store,
            stream_type="Method",
            stream_id=method_id,
            expected_version=1,
            event_type=method_event_type_name(schema_event),
            payload=method_to_payload(schema_event),
            command_name="UpdateMethodParametersSchema",
        )


async def _seed_practice(
    store: InMemoryEventStore,
    practice_id: UUID,
    *,
    method_id: UUID,
) -> None:
    event = PracticeDefined(
        practice_id=practice_id,
        name="Test Practice",
        method_id=method_id,
        site_id=uuid4(),
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Practice",
        stream_id=practice_id,
        expected_version=0,
        event_type=practice_event_type_name(event),
        payload=practice_to_payload(event),
        command_name="DefinePractice",
    )


async def _seed_plan(
    store: InMemoryEventStore,
    plan_id: UUID,
    *,
    practice_id: UUID,
    asset_ids: tuple[UUID, ...],
    method_id: UUID,
) -> None:
    event = PlanDefined(
        plan_id=plan_id,
        name="Test Plan",
        practice_id=practice_id,
        asset_ids=tuple(sorted(asset_ids, key=str)),
        method_id=method_id,
        method_needed_family_ids_snapshot=(),
        asset_families_snapshot={},
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Plan",
        stream_id=plan_id,
        expected_version=0,
        event_type=plan_event_type_name(event),
        payload=plan_to_payload(event),
        command_name="DefinePlan",
    )


async def _seed_run_started(
    store: InMemoryEventStore,
    run_id: UUID,
    *,
    plan_id: UUID,
    effective_parameters: dict[str, Any] | None = None,
) -> None:
    event = RunStarted(
        run_id=run_id,
        name="Test Run",
        plan_id=plan_id,
        subject_id=uuid4(),
        occurred_at=_NOW,
        effective_parameters=effective_parameters or {},
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(stream_type="Run", stream_id=run_id, expected_version=0, events=[new_event])


def _energy_schema() -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "minimum": 5,
                "maximum": 50,
                "unit": {"system": "udunits", "code": "keV"},
            }
        },
    }


async def _seed_full_chain(
    store: InMemoryEventStore,
    *,
    schema: dict[str, Any] | None,
    effective_parameters: dict[str, Any] | None = None,
) -> tuple[UUID, UUID, UUID, UUID]:
    """Seed Method (with optional schema) → Practice → Plan → Run.

    Returns (method_id, practice_id, plan_id, run_id)."""
    method_id = uuid4()
    practice_id = uuid4()
    plan_id = uuid4()
    run_id = _RUN_ID

    await _seed_method(store, method_id, parameters_schema=schema)
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_plan(store, plan_id, practice_id=practice_id, asset_ids=(), method_id=method_id)
    await _seed_run_started(
        store, run_id, plan_id=plan_id, effective_parameters=effective_parameters
    )
    return method_id, practice_id, plan_id, run_id


# ---------- Happy paths ----------


@pytest.mark.unit
async def test_handler_appends_run_adjusted_event_with_merged_snapshot() -> None:
    store = InMemoryEventStore()
    _, _, _, run_id = await _seed_full_chain(
        store, schema=_energy_schema(), effective_parameters={"energy": 10.0}
    )
    deps = build_deps(ids=[_ADJUSTED_EVENT_ID], now=_NOW, event_store=store)

    result = await adjust_run.bind(deps)(
        AdjustRun(
            run_id=run_id,
            parameters_patch={"energy": 12.0},
            reason="re-center on detected feature",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result is None
    events, version = await store.load("Run", run_id)
    assert version == 2
    assert [e.event_type for e in events] == ["RunStarted", "RunAdjusted"]
    adjusted = events[1]
    assert adjusted.event_id == _ADJUSTED_EVENT_ID
    assert adjusted.metadata == {"command": "AdjustRun"}
    assert adjusted.payload["parameters_patch"] == {"energy": 12.0}
    assert adjusted.payload["effective_parameters"] == {"energy": 12.0}
    assert adjusted.payload["reason"] == "re-center on detected feature"
    assert adjusted.payload["decided_by_decision_id"] is None


@pytest.mark.unit
async def test_handler_threads_decision_id_to_event_without_loading_decision() -> None:
    """Eventual-consistency stance: no Decision aggregate is seeded;
    handler does not load it; the link flows through to the payload
    verbatim (cross-BC reference verification belongs in projection
    consumers, not the write path)."""
    store = InMemoryEventStore()
    _, _, _, run_id = await _seed_full_chain(store, schema=None, effective_parameters={})
    decision_id = uuid4()
    deps = build_deps(ids=[_ADJUSTED_EVENT_ID], now=_NOW, event_store=store)

    await adjust_run.bind(deps)(
        AdjustRun(
            run_id=run_id,
            parameters_patch={"steering_step": 1},
            reason="agent loop iteration",
            decided_by_decision_id=decision_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Run", run_id)
    assert events[1].payload["decided_by_decision_id"] == str(decision_id)


# ---------- Failure paths ----------


@pytest.mark.unit
async def test_handler_raises_run_not_found_when_run_does_not_exist() -> None:
    deps = build_deps(ids=[_ADJUSTED_EVENT_ID], now=_NOW)
    with pytest.raises(RunNotFoundError):
        await adjust_run.bind(deps)(
            AdjustRun(
                run_id=_RUN_ID,
                parameters_patch={"x": 1},
                reason="x",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    _, _, _, run_id = await _seed_full_chain(store, schema=None, effective_parameters={})
    deny_deps = build_deps(ids=[_ADJUSTED_EVENT_ID], now=_NOW, event_store=store, deny=True)

    with pytest.raises(UnauthorizedError) as exc_info:
        await adjust_run.bind(deny_deps)(
            AdjustRun(
                run_id=run_id,
                parameters_patch={"x": 1},
                reason="x",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"

    # Side-effect check: deny path MUST NOT write an event.
    events, version = await store.load("Run", run_id)
    assert version == 1
    assert [e.event_type for e in events] == ["RunStarted"]


@pytest.mark.unit
async def test_handler_raises_plan_not_found_when_plan_stream_empty() -> None:
    """Cross-aggregate load-miss: Run seeded but its plan_id points to
    an empty stream. Defensive — production should never see this, but
    a clean 404 beats a 500 if the Plan stream is somehow gone."""
    store = InMemoryEventStore()
    plan_id = uuid4()
    await _seed_run_started(store, _RUN_ID, plan_id=plan_id)
    deps = build_deps(ids=[_ADJUSTED_EVENT_ID], now=_NOW, event_store=store)

    with pytest.raises(PlanNotFoundError):
        await adjust_run.bind(deps)(
            AdjustRun(
                run_id=_RUN_ID,
                parameters_patch={"x": 1},
                reason="x",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_practice_not_found_when_practice_stream_empty() -> None:
    """Cross-aggregate load-miss: Run + Plan seeded but Plan's
    practice_id points to an empty stream."""
    store = InMemoryEventStore()
    plan_id = uuid4()
    practice_id = uuid4()
    method_id = uuid4()
    await _seed_plan(store, plan_id, practice_id=practice_id, asset_ids=(), method_id=method_id)
    await _seed_run_started(store, _RUN_ID, plan_id=plan_id)
    deps = build_deps(ids=[_ADJUSTED_EVENT_ID], now=_NOW, event_store=store)

    with pytest.raises(PracticeNotFoundError):
        await adjust_run.bind(deps)(
            AdjustRun(
                run_id=_RUN_ID,
                parameters_patch={"x": 1},
                reason="x",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_method_not_found_when_method_stream_empty() -> None:
    """Cross-aggregate load-miss: Run + Plan + Practice seeded but
    Practice's method_id points to an empty stream."""
    store = InMemoryEventStore()
    plan_id = uuid4()
    practice_id = uuid4()
    method_id = uuid4()
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_plan(store, plan_id, practice_id=practice_id, asset_ids=(), method_id=method_id)
    await _seed_run_started(store, _RUN_ID, plan_id=plan_id)
    deps = build_deps(ids=[_ADJUSTED_EVENT_ID], now=_NOW, event_store=store)

    with pytest.raises(MethodNotFoundError):
        await adjust_run.bind(deps)(
            AdjustRun(
                run_id=_RUN_ID,
                parameters_patch={"x": 1},
                reason="x",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_does_not_auto_populate_decided_by_from_causation_id() -> None:
    """Anti-hook verification (anti-hook #6): `causation_id` is the
    technical envelope chain (previous-message id); it MUST NOT leak
    into the domain `decided_by_decision_id` payload field. Passing
    causation_id with decided_by_decision_id=None must persist
    decided_by_decision_id=None on the event payload."""
    store = InMemoryEventStore()
    _, _, _, run_id = await _seed_full_chain(store, schema=None, effective_parameters={})
    causation_id = uuid4()
    deps = build_deps(ids=[_ADJUSTED_EVENT_ID], now=_NOW, event_store=store)

    await adjust_run.bind(deps)(
        AdjustRun(
            run_id=run_id,
            parameters_patch={"x": 1},
            reason="x",
            decided_by_decision_id=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation_id,
    )

    events, _ = await store.load("Run", run_id)
    assert events[1].payload["decided_by_decision_id"] is None


@pytest.mark.unit
def test_wire_run_includes_adjust_run() -> None:
    deps = build_deps(ids=[_ADJUSTED_EVENT_ID], now=_NOW)
    handlers = wire_run(deps)
    assert isinstance(handlers, RunHandlers)
    assert callable(handlers.adjust_run)
