"""Unit tests for the `get_plan` query handler.

Mirrors `test_get_practice_handler.py` shape. Round-trip define +
get verifies fold-on-read returns the defined Plan with the right
practice_id and asset_ids. Bind-time audit snapshots in the
PlanDefined event are NOT exposed by get_plan (gate-review Q4).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.ports import (
    Allow,
    AuthzResult,
)
from cora.recipe import RecipeHandlers, UnauthorizedError, wire_recipe
from cora.recipe.aggregates.plan import (
    Plan,
    PlanName,
    PlanStatus,
)
from cora.recipe.aggregates.plan.events import (
    PlanDefined,
    event_type_name,
    to_payload,
)
from cora.recipe.features import get_plan
from cora.recipe.features.get_plan import GetPlan
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PLAN_ID = UUID("01900000-0000-7000-8000-00000000ef01")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-00000000ef02")
_ASSET_ID = UUID("01900000-0000-7000-8000-00000000ef03")
_METHOD_ID = UUID("01900000-0000-7000-8000-00000000ef04")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_plan(
    store: InMemoryEventStore,
    plan_id: UUID,
    *,
    practice_id: UUID,
    asset_id: UUID,
    method_id: UUID,
    name: str = "32-ID FlyScan",
) -> None:
    """Direct event-seed for a Plan without going through the
    define_plan handler (which would require seeding upstream
    Practice/Method/Asset)."""
    event = PlanDefined(
        plan_id=plan_id,
        name=name,
        practice_id=practice_id,
        asset_ids=[asset_id],
        method_id=method_id,
        method_needed_families_snapshot=[],
        asset_families_snapshot={asset_id: []},
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="DefinePlan",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Plan",
        stream_id=plan_id,
        expected_version=0,
        events=[new_event],
    )


@pytest.mark.unit
async def test_handler_returns_plan_for_known_id() -> None:
    """Round-trip: seed + get."""
    store = InMemoryEventStore()
    await _seed_plan(
        store, _PLAN_ID, practice_id=_PRACTICE_ID, asset_id=_ASSET_ID, method_id=_METHOD_ID
    )
    deps = build_deps(ids=[_PLAN_ID], now=_NOW, event_store=store)
    handler = get_plan.bind(deps)
    plan = await handler(
        GetPlan(plan_id=_PLAN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert plan == Plan(
        id=_PLAN_ID,
        name=PlanName("32-ID FlyScan"),
        practice_id=_PRACTICE_ID,
        asset_ids=frozenset({_ASSET_ID}),
        status=PlanStatus.DEFINED,
        method_id=_METHOD_ID,
    )


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_id() -> None:
    deps = build_deps(ids=[_PLAN_ID], now=_NOW)
    handler = get_plan.bind(deps)
    plan = await handler(
        GetPlan(plan_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert plan is None


class _RecordingAuthorize:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str, UUID]] = []

    async def __call__(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        surface_id: UUID = UUID(int=0),  # noqa: B008
    ) -> AuthzResult:
        self.calls.append((principal_id, command_name, conduit_id))
        return Allow()


@pytest.mark.unit
async def test_handler_authorizes_with_query_name_and_default_conduit() -> None:
    tracking = _RecordingAuthorize()
    deps = build_deps(ids=[_PLAN_ID], now=_NOW, authorize=tracking)

    handler = get_plan.bind(deps)
    await handler(
        GetPlan(plan_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert tracking.calls == [(_PRINCIPAL_ID, "GetPlan", UUID(int=0))]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[_PLAN_ID], now=_NOW, deny=True)

    handler = get_plan.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetPlan(plan_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
def test_wire_recipe_includes_get_plan() -> None:
    deps = build_deps(ids=[_PLAN_ID], now=_NOW)
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(handlers.get_plan)
