"""Unit tests for the `restore_from_maintenance` application handler.

Mirror of `enter_maintenance` handler tests (same single-source
update-style template). Asset path: register + activate + enter +
restore (4 prior events; restore is the 5th).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.asset import (
    AssetCannotRestoreFromMaintenanceError,
    AssetLevel,
    AssetLifecycle,
    AssetNotFoundError,
)
from cora.equipment.features import (
    activate_asset,
    enter_maintenance,
    register_asset,
    restore_from_maintenance,
)
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.enter_maintenance import EnterMaintenance
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.restore_from_maintenance import RestoreFromMaintenance
from cora.infrastructure.config import Settings
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

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000009ca1")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000009ce1")
_ACTIVATE_EVENT_ID = UUID("01900000-0000-7000-8000-000000009ce2")
_ENTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000009ce3")
_RESTORE_EVENT_ID = UUID("01900000-0000-7000-8000-000000009ce4")
_PARENT_ID = UUID("01900000-0000-7000-8000-00000000a000")
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
    settings = Settings(app_env="test")  # type: ignore[call-arg]
    return Kernel(
        settings=settings,
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator(
            [
                _NEW_ID,
                _REGISTER_EVENT_ID,
                _ACTIVATE_EVENT_ID,
                _ENTER_EVENT_ID,
                _RESTORE_EVENT_ID,
            ]
        ),
        authorize=DenyAllAuthorize() if deny else AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


async def _register_activate_enter(deps: Kernel) -> UUID:
    """Helper: drive an asset all the way to Maintenance lifecycle."""
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await enter_maintenance.bind(deps)(
        EnterMaintenance(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return asset_id


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_activate_enter(deps)

    result = await restore_from_maintenance.bind(deps)(
        RestoreFromMaintenance(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_asset_restored_event() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_activate_enter(deps)

    await restore_from_maintenance.bind(deps)(
        RestoreFromMaintenance(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", asset_id)
    assert version == 4
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetActivated",
        "AssetMaintenanceEntered",
        "AssetRestoredFromMaintenance",
    ]
    restored = events[3]
    assert restored.event_id == _RESTORE_EVENT_ID
    assert restored.metadata == {"command": "RestoreFromMaintenance"}


@pytest.mark.unit
async def test_handler_raises_asset_not_found_when_asset_does_not_exist() -> None:
    deps = _build_deps()
    handler = restore_from_maintenance.bind(deps)

    with pytest.raises(AssetNotFoundError):
        await handler(
            RestoreFromMaintenance(asset_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_restore_when_already_active() -> None:
    """Strict semantics: restore on already-Active raises (the
    maintenance window has already ended)."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    with pytest.raises(AssetCannotRestoreFromMaintenanceError) as exc_info:
        await restore_from_maintenance.bind(deps)(
            RestoreFromMaintenance(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.current_lifecycle is AssetLifecycle.ACTIVE


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_activate_enter(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError) as exc_info:
        await restore_from_maintenance.bind(deny_deps)(
            RestoreFromMaintenance(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_activate_enter(deps)

    await restore_from_maintenance.bind(deps)(
        RestoreFromMaintenance(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Asset", asset_id)
    assert events[3].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_includes_restore_from_maintenance() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.restore_from_maintenance)
