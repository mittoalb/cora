"""Unit tests for the `start_run` application handler.

This handler pre-loads the full upstream chain — Plan → Practice →
Method → each bound Asset → Subject (if subject_id given) — before
reaching the pure decider. Second instance of the cross-aggregate-
validation pattern (after `define_plan` in 6e-1).

Test setup uses direct event-seeding helpers via `_seed_*`
functions that append events directly to the in-memory store,
bypassing the upstream BCs' handlers. Mirrors
test_define_plan_handler.py's seeding approach. Keeps the test
focus on start_run handler behavior, not upstream BC behavior.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    AssetLevel,
    AssetNotFoundError,
)
from cora.equipment.aggregates.asset.events import (
    AssetCapabilityAdded,
    AssetRegistered,
)
from cora.equipment.aggregates.asset.events import (
    event_type_name as asset_event_type_name,
)
from cora.equipment.aggregates.asset.events import (
    to_payload as asset_to_payload,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    AuthzResult,
    Deny,
    FixedIdGenerator,
    FrozenClock,
)
from cora.recipe.aggregates.method import MethodNotFoundError
from cora.recipe.aggregates.method.events import MethodDefined
from cora.recipe.aggregates.method.events import (
    event_type_name as method_event_type_name,
)
from cora.recipe.aggregates.method.events import to_payload as method_to_payload
from cora.recipe.aggregates.plan import PlanNotFoundError
from cora.recipe.aggregates.plan.events import PlanDefined, PlanDeprecated
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
from cora.run.aggregates.run import (
    PlanDeprecatedError,
    RunAssetDecommissionedError,
    RunCapabilitiesNotSatisfiedError,
    SubjectNotMountableError,
)
from cora.run.features import start_run
from cora.run.features.start_run import StartRun
from cora.subject.aggregates.subject import SubjectNotFoundError
from cora.subject.aggregates.subject.events import (
    SubjectMounted,
    SubjectRegistered,
)
from cora.subject.aggregates.subject.events import (
    event_type_name as subject_event_type_name,
)
from cora.subject.aggregates.subject.events import (
    to_payload as subject_to_payload,
)

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000000f01")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000000f02")
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
) -> Kernel:
    """start_run consumes 2 ids (run_id + event_id)."""
    settings = Settings(app_env="test")  # type: ignore[call-arg]
    return Kernel(
        settings=settings,
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_NEW_ID, _EVENT_ID]),
        authorize=DenyAllAuthorize() if deny else AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


# ---------- Direct event-seeding helpers ----------


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
    needs_capabilities: frozenset[UUID] = frozenset(),
) -> None:
    event = MethodDefined(
        method_id=method_id,
        name="Test Method",
        needs_capabilities=sorted(needs_capabilities, key=str),
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Method",
        stream_id=method_id,
        expected_version=0,
        event_type=method_event_type_name(event),
        payload=method_to_payload(event),
        command_name="DefineMethod",
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


async def _seed_asset(
    store: InMemoryEventStore,
    asset_id: UUID,
    *,
    capabilities: frozenset[UUID] = frozenset(),
    decommissioned: bool = False,
) -> None:
    register_event = AssetRegistered(
        asset_id=asset_id,
        name="TestAsset",
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Asset",
        stream_id=asset_id,
        expected_version=0,
        event_type=asset_event_type_name(register_event),
        payload=asset_to_payload(register_event),
        command_name="RegisterAsset",
    )
    version = 1
    for cap_id in sorted(capabilities, key=str):
        cap_event = AssetCapabilityAdded(asset_id=asset_id, capability_id=cap_id, occurred_at=_NOW)
        await _append(
            store,
            stream_type="Asset",
            stream_id=asset_id,
            expected_version=version,
            event_type=asset_event_type_name(cap_event),
            payload=asset_to_payload(cap_event),
            command_name="AddAssetCapability",
        )
        version += 1
    if decommissioned:
        from cora.equipment.aggregates.asset.events import AssetDecommissioned

        dc_event = AssetDecommissioned(asset_id=asset_id, occurred_at=_NOW)
        await _append(
            store,
            stream_type="Asset",
            stream_id=asset_id,
            expected_version=version,
            event_type=asset_event_type_name(dc_event),
            payload=asset_to_payload(dc_event),
            command_name="DecommissionAsset",
        )


async def _seed_plan(
    store: InMemoryEventStore,
    plan_id: UUID,
    *,
    practice_id: UUID,
    asset_ids: list[UUID],
    method_id: UUID,
    deprecated: bool = False,
) -> None:
    event = PlanDefined(
        plan_id=plan_id,
        name="Test Plan",
        practice_id=practice_id,
        asset_ids=sorted(asset_ids, key=str),
        method_id=method_id,
        method_needs_capabilities_snapshot=[],
        asset_capabilities_snapshot={},
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
    if deprecated:
        deprecated_event = PlanDeprecated(plan_id=plan_id, occurred_at=_NOW)
        await _append(
            store,
            stream_type="Plan",
            stream_id=plan_id,
            expected_version=1,
            event_type=plan_event_type_name(deprecated_event),
            payload=plan_to_payload(deprecated_event),
            command_name="DeprecatePlan",
        )


async def _seed_subject_mounted(
    store: InMemoryEventStore,
    subject_id: UUID,
) -> None:
    register_event = SubjectRegistered(subject_id=subject_id, name="TestSubject", occurred_at=_NOW)
    await _append(
        store,
        stream_type="Subject",
        stream_id=subject_id,
        expected_version=0,
        event_type=subject_event_type_name(register_event),
        payload=subject_to_payload(register_event),
        command_name="RegisterSubject",
    )
    mount_event = SubjectMounted(subject_id=subject_id, asset_id=uuid4(), occurred_at=_NOW)
    await _append(
        store,
        stream_type="Subject",
        stream_id=subject_id,
        expected_version=1,
        event_type=subject_event_type_name(mount_event),
        payload=subject_to_payload(mount_event),
        command_name="MountSubject",
    )


async def _seed_full_chain(
    store: InMemoryEventStore,
    *,
    plan_deprecated: bool = False,
    asset_decommissioned: bool = False,
    drift_capability_off_asset: bool = False,
) -> tuple[UUID, UUID, UUID, UUID, UUID, UUID]:
    """Seed Capability → Asset (with capability) → Method → Practice → Plan
    + Subject. Returns (cap_id, asset_id, method_id, practice_id, plan_id,
    subject_id). Subject is always Mounted; tests can override.

    Set `drift_capability_off_asset=True` to seed an Asset whose
    capabilities don't satisfy the Method's needs (simulates drift
    since Plan-bind).
    """
    cap_id = uuid4()
    asset_id = uuid4()
    method_id = uuid4()
    practice_id = uuid4()
    plan_id = uuid4()
    subject_id = uuid4()

    asset_caps: frozenset[UUID] = frozenset() if drift_capability_off_asset else frozenset({cap_id})
    await _seed_asset(store, asset_id, capabilities=asset_caps, decommissioned=asset_decommissioned)
    await _seed_method(store, method_id, needs_capabilities=frozenset({cap_id}))
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_plan(
        store,
        plan_id,
        practice_id=practice_id,
        asset_ids=[asset_id],
        method_id=method_id,
        deprecated=plan_deprecated,
    )
    await _seed_subject_mounted(store, subject_id)
    return (cap_id, asset_id, method_id, practice_id, plan_id, subject_id)


# ---------- Happy paths ----------


@pytest.mark.unit
async def test_handler_returns_generated_run_id_for_sample_run() -> None:
    store = InMemoryEventStore()
    _, _, _, _, plan_id, subject_id = await _seed_full_chain(store)
    deps = _build_deps(event_store=store)
    handler = start_run.bind(deps)

    result = await handler(
        StartRun(name="Run-A", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_returns_generated_run_id_for_dark_field_run() -> None:
    """Run without Subject (calibration / dark-field)."""
    store = InMemoryEventStore()
    _, _, _, _, plan_id, _ = await _seed_full_chain(store)
    deps = _build_deps(event_store=store)
    handler = start_run.bind(deps)

    result = await handler(
        StartRun(name="Dark field", plan_id=plan_id, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_run_started_event_to_store() -> None:
    store = InMemoryEventStore()
    _, _, _, _, plan_id, subject_id = await _seed_full_chain(store)
    deps = _build_deps(event_store=store)
    handler = start_run.bind(deps)

    await handler(
        StartRun(name="Run-A", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Run", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "RunStarted"
    assert stored.payload["run_id"] == str(_NEW_ID)
    assert stored.payload["name"] == "Run-A"
    assert stored.payload["plan_id"] == str(plan_id)
    assert stored.payload["subject_id"] == str(subject_id)
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "StartRun"}


@pytest.mark.unit
async def test_handler_appends_run_started_with_null_subject_for_dark_field() -> None:
    store = InMemoryEventStore()
    _, _, _, _, plan_id, _ = await _seed_full_chain(store)
    deps = _build_deps(event_store=store)
    handler = start_run.bind(deps)

    await handler(
        StartRun(name="Dark field", plan_id=plan_id, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Run", _NEW_ID)
    assert events[0].payload["subject_id"] is None


# ---------- Authorization ----------


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)
    handler = start_run.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            StartRun(name="X", plan_id=uuid4(), subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_pre_load_when_denied() -> None:
    """Authorize runs BEFORE the cross-aggregate pre-loads."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = start_run.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            StartRun(name="X", plan_id=uuid4(), subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Run", _NEW_ID)
    assert events == []
    assert version == 0


# ---------- Pre-load: NotFoundError paths ----------


@pytest.mark.unit
async def test_handler_raises_plan_not_found_when_plan_missing() -> None:
    deps = _build_deps()
    handler = start_run.bind(deps)

    missing_plan_id = uuid4()
    with pytest.raises(PlanNotFoundError):
        await handler(
            StartRun(name="X", plan_id=missing_plan_id, subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_practice_not_found_when_referenced_practice_missing() -> None:
    """Plan references a practice_id that's not in the store (defensive corruption case)."""
    store = InMemoryEventStore()
    asset_id = uuid4()
    method_id = uuid4()
    plan_id = uuid4()
    bogus_practice_id = uuid4()
    await _seed_asset(store, asset_id, capabilities=frozenset())
    await _seed_method(store, method_id)
    # Plan references a practice that doesn't exist.
    await _seed_plan(
        store,
        plan_id,
        practice_id=bogus_practice_id,
        asset_ids=[asset_id],
        method_id=method_id,
    )
    deps = _build_deps(event_store=store)
    handler = start_run.bind(deps)

    with pytest.raises(PracticeNotFoundError):
        await handler(
            StartRun(name="X", plan_id=plan_id, subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_method_not_found_when_referenced_method_missing() -> None:
    store = InMemoryEventStore()
    asset_id = uuid4()
    practice_id = uuid4()
    plan_id = uuid4()
    bogus_method_id = uuid4()
    await _seed_asset(store, asset_id, capabilities=frozenset())
    await _seed_practice(store, practice_id, method_id=bogus_method_id)
    await _seed_plan(
        store,
        plan_id,
        practice_id=practice_id,
        asset_ids=[asset_id],
        method_id=bogus_method_id,
    )
    deps = _build_deps(event_store=store)
    handler = start_run.bind(deps)

    with pytest.raises(MethodNotFoundError):
        await handler(
            StartRun(name="X", plan_id=plan_id, subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_asset_not_found_when_bound_asset_missing() -> None:
    store = InMemoryEventStore()
    method_id = uuid4()
    practice_id = uuid4()
    plan_id = uuid4()
    bogus_asset_id = uuid4()
    await _seed_method(store, method_id)
    await _seed_practice(store, practice_id, method_id=method_id)
    # Plan references an Asset that doesn't exist.
    await _seed_plan(
        store,
        plan_id,
        practice_id=practice_id,
        asset_ids=[bogus_asset_id],
        method_id=method_id,
    )
    deps = _build_deps(event_store=store)
    handler = start_run.bind(deps)

    with pytest.raises(AssetNotFoundError):
        await handler(
            StartRun(name="X", plan_id=plan_id, subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_subject_not_found_when_subject_id_missing() -> None:
    store = InMemoryEventStore()
    _, _, _, _, plan_id, _ = await _seed_full_chain(store)
    deps = _build_deps(event_store=store)
    handler = start_run.bind(deps)

    bogus_subject_id = uuid4()
    with pytest.raises(SubjectNotFoundError):
        await handler(
            StartRun(name="X", plan_id=plan_id, subject_id=bogus_subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Decider error propagation ----------


@pytest.mark.unit
async def test_handler_propagates_plan_deprecated_error() -> None:
    store = InMemoryEventStore()
    _, _, _, _, plan_id, _ = await _seed_full_chain(store, plan_deprecated=True)
    deps = _build_deps(event_store=store)
    handler = start_run.bind(deps)

    with pytest.raises(PlanDeprecatedError):
        await handler(
            StartRun(name="X", plan_id=plan_id, subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_subject_not_mountable_error() -> None:
    store = InMemoryEventStore()
    _, _, _, _, plan_id, subject_id = await _seed_full_chain(store)
    # Mounted Subject from _seed_full_chain — let's flip it to Removed.
    from cora.subject.aggregates.subject.events import (
        SubjectMeasured,
        SubjectRemoved,
    )

    measured = SubjectMeasured(subject_id=subject_id, occurred_at=_NOW)
    await _append(
        store,
        stream_type="Subject",
        stream_id=subject_id,
        expected_version=2,
        event_type=subject_event_type_name(measured),
        payload=subject_to_payload(measured),
        command_name="MeasureSubject",
    )
    removed = SubjectRemoved(subject_id=subject_id, occurred_at=_NOW)
    await _append(
        store,
        stream_type="Subject",
        stream_id=subject_id,
        expected_version=3,
        event_type=subject_event_type_name(removed),
        payload=subject_to_payload(removed),
        command_name="RemoveSubject",
    )
    deps = _build_deps(event_store=store)
    handler = start_run.bind(deps)

    with pytest.raises(SubjectNotMountableError):
        await handler(
            StartRun(name="X", plan_id=plan_id, subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_run_asset_decommissioned_error() -> None:
    store = InMemoryEventStore()
    _, _, _, _, plan_id, _ = await _seed_full_chain(store, asset_decommissioned=True)
    deps = _build_deps(event_store=store)
    handler = start_run.bind(deps)

    with pytest.raises(RunAssetDecommissionedError):
        await handler(
            StartRun(name="X", plan_id=plan_id, subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_capabilities_not_satisfied_at_run_start() -> None:
    """Re-validation: Asset capabilities drifted off after Plan-bind."""
    store = InMemoryEventStore()
    _, _, _, _, plan_id, _ = await _seed_full_chain(store, drift_capability_off_asset=True)
    deps = _build_deps(event_store=store)
    handler = start_run.bind(deps)

    with pytest.raises(RunCapabilitiesNotSatisfiedError):
        await handler(
            StartRun(name="X", plan_id=plan_id, subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Causation propagation ----------


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    _, _, _, _, plan_id, _ = await _seed_full_chain(store)
    deps = _build_deps(event_store=store)
    handler = start_run.bind(deps)

    await handler(
        StartRun(name="X", plan_id=plan_id, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Run", _NEW_ID)
    assert events[0].causation_id == causation


# ---------- Wire smoke ----------


@pytest.mark.unit
def test_wire_run_returns_handlers_bundle() -> None:
    deps = _build_deps()
    handlers = wire_run(deps)
    assert isinstance(handlers, RunHandlers)
    assert callable(handlers.start_run)
    assert callable(handlers.get_run)
