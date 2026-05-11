"""Unit tests for the `version_plan` application handler.

Mirror of `test_version_practice_handler.py`. Longhand handler
(logs version_tag).

Setup uses direct event-seeding via `_seed_plan` rather than the
full upstream chain (define_plan handler tests already cover the
Plan creation path with all pre-loads). This test file focuses on
version_plan handler behavior given an existing Plan.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.config import Settings
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    AuthzResult,
    Deny,
    FixedIdGenerator,
    FrozenClock,
)
from cora.recipe import RecipeHandlers, UnauthorizedError, wire_recipe
from cora.recipe.aggregates.plan import (
    InvalidPlanVersionTagError,
    PlanCannotVersionError,
    PlanNotFoundError,
)
from cora.recipe.aggregates.plan.events import (
    PlanDefined,
    PlanDeprecated,
    event_type_name,
    to_payload,
)
from cora.recipe.features import deprecate_plan, version_plan
from cora.recipe.features.version_plan import VersionPlan

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PLAN_ID = UUID("01900000-0000-7000-8000-00000000f001")
_VERSIONED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000f002")
_DEPRECATED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000f003")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


class DenyAllAuthorize:
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
        id_generator=FixedIdGenerator([_VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID]),
        authorize=DenyAllAuthorize() if deny else AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


async def _seed_plan(store: InMemoryEventStore, plan_id: UUID) -> None:
    """Direct event-seed for a Plan without the upstream handler chain."""
    event = PlanDefined(
        plan_id=plan_id,
        name="32-ID FlyScan",
        practice_id=uuid4(),
        asset_ids=[uuid4()],
        method_id=uuid4(),
        method_needs_capabilities_snapshot=[],
        asset_capabilities_snapshot={},
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="DefinePlan",
        correlation_id=_CORRELATION_ID,
    )
    await store.append(
        stream_type="Plan", stream_id=plan_id, expected_version=0, events=[new_event]
    )


async def _seed_plan_deprecated(store: InMemoryEventStore, plan_id: UUID) -> None:
    """Seed a Plan in the Deprecated state."""
    await _seed_plan(store, plan_id)
    deprecated = PlanDeprecated(plan_id=plan_id, occurred_at=_NOW)
    new_event = to_new_event(
        event_type=event_type_name(deprecated),
        payload=to_payload(deprecated),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="DeprecatePlan",
        correlation_id=_CORRELATION_ID,
    )
    await store.append(
        stream_type="Plan", stream_id=plan_id, expected_version=1, events=[new_event]
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    await _seed_plan(store, _PLAN_ID)
    deps = _build_deps(event_store=store)

    result = await version_plan.bind(deps)(
        VersionPlan(plan_id=_PLAN_ID, version_tag="v2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_plan_versioned_event_with_version_tag() -> None:
    store = InMemoryEventStore()
    await _seed_plan(store, _PLAN_ID)
    deps = _build_deps(event_store=store)

    await version_plan.bind(deps)(
        VersionPlan(plan_id=_PLAN_ID, version_tag="v2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Plan", _PLAN_ID)
    assert version == 2
    assert [e.event_type for e in events] == ["PlanDefined", "PlanVersioned"]
    versioned = events[1]
    assert versioned.event_id == _VERSIONED_EVENT_ID
    assert versioned.metadata == {"command": "VersionPlan"}
    assert versioned.payload["version_tag"] == "v2"


@pytest.mark.unit
async def test_handler_supports_re_versioning() -> None:
    """Defined → Versioned → Versioned (subsequent revision)."""
    store = InMemoryEventStore()
    await _seed_plan(store, _PLAN_ID)
    deps = _build_deps(event_store=store)
    handler = version_plan.bind(deps)

    await handler(
        VersionPlan(plan_id=_PLAN_ID, version_tag="v1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await handler(
        VersionPlan(plan_id=_PLAN_ID, version_tag="v2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Plan", _PLAN_ID)
    assert version == 3
    assert events[1].payload["version_tag"] == "v1"
    assert events[2].payload["version_tag"] == "v2"


@pytest.mark.unit
async def test_handler_raises_plan_not_found_when_plan_does_not_exist() -> None:
    deps = _build_deps()
    handler = version_plan.bind(deps)

    with pytest.raises(PlanNotFoundError):
        await handler(
            VersionPlan(plan_id=_PLAN_ID, version_tag="v1"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_version_tag_for_whitespace_only() -> None:
    store = InMemoryEventStore()
    await _seed_plan(store, _PLAN_ID)
    deps = _build_deps(event_store=store)

    with pytest.raises(InvalidPlanVersionTagError):
        await version_plan.bind(deps)(
            VersionPlan(plan_id=_PLAN_ID, version_tag="   "),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_version_when_deprecated() -> None:
    store = InMemoryEventStore()
    await _seed_plan_deprecated(store, _PLAN_ID)
    deps = _build_deps(event_store=store)

    with pytest.raises(PlanCannotVersionError):
        await version_plan.bind(deps)(
            VersionPlan(plan_id=_PLAN_ID, version_tag="v2"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_plan(store, _PLAN_ID)
    deny_deps = _build_deps(event_store=store, deny=True)

    with pytest.raises(UnauthorizedError) as exc_info:
        await version_plan.bind(deny_deps)(
            VersionPlan(plan_id=_PLAN_ID, version_tag="v2"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    await _seed_plan(store, _PLAN_ID)
    deps = _build_deps(event_store=store)

    await version_plan.bind(deps)(
        VersionPlan(plan_id=_PLAN_ID, version_tag="v2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Plan", _PLAN_ID)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_recipe_includes_version_plan() -> None:
    deps = _build_deps()
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(handlers.version_plan)


# Smoke for module-as-namespace import.
_ = deprecate_plan.DeprecatePlan
