"""Unit tests for the `remove_asset_capability` application handler.

Mirror of `test_add_asset_capability_handler.py`. Shared longhand
shape (extra capability_id log field).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.asset import (
    AssetCannotRemoveCapabilityError,
    AssetLevel,
    AssetNotFoundError,
)
from cora.equipment.features import (
    add_asset_capability,
    register_asset,
    remove_asset_capability,
)
from cora.equipment.features.add_asset_capability import AddAssetCapability
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.remove_asset_capability import RemoveAssetCapability
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import SharedDeps
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
_NEW_ID = UUID("01900000-0000-7000-8000-00000000fb01")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-00000000fb02")
_ADD_EVENT_ID = UUID("01900000-0000-7000-8000-00000000fb03")
_REMOVE_EVENT_ID = UUID("01900000-0000-7000-8000-00000000fb04")
_PARENT_ID = UUID("01900000-0000-7000-8000-00000000a000")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAP1 = UUID("01900000-0000-7000-8000-000000000111")


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
        id_generator=FixedIdGenerator(
            [_NEW_ID, _REGISTER_EVENT_ID, _ADD_EVENT_ID, _REMOVE_EVENT_ID]
        ),
        authorize=DenyAllAuthorize() if deny else AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


async def _register_and_add_capability(deps: SharedDeps) -> UUID:
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_capability.bind(deps)(
        AddAssetCapability(asset_id=asset_id, capability_id=_CAP1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return asset_id


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_and_add_capability(deps)

    result = await remove_asset_capability.bind(deps)(
        RemoveAssetCapability(asset_id=asset_id, capability_id=_CAP1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_asset_capability_removed_event_with_capability_id() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_and_add_capability(deps)

    await remove_asset_capability.bind(deps)(
        RemoveAssetCapability(asset_id=asset_id, capability_id=_CAP1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Asset", asset_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetCapabilityAdded",
        "AssetCapabilityRemoved",
    ]
    removed = events[2]
    assert removed.event_id == _REMOVE_EVENT_ID
    assert removed.metadata == {"command": "RemoveAssetCapability"}
    assert removed.payload["capability_id"] == str(_CAP1)


@pytest.mark.unit
async def test_handler_raises_asset_not_found_when_asset_does_not_exist() -> None:
    deps = _build_deps()
    handler = remove_asset_capability.bind(deps)

    with pytest.raises(AssetNotFoundError):
        await handler(
            RemoveAssetCapability(asset_id=uuid4(), capability_id=_CAP1),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_remove_when_capability_not_present() -> None:
    """Strict-not-idempotent: removing a capability not in the set raises."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    with pytest.raises(AssetCannotRemoveCapabilityError) as exc_info:
        await remove_asset_capability.bind(deps)(
            RemoveAssetCapability(asset_id=asset_id, capability_id=_CAP1),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert "not in" in exc_info.value.reason


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_and_add_capability(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError) as exc_info:
        await remove_asset_capability.bind(deny_deps)(
            RemoveAssetCapability(asset_id=asset_id, capability_id=_CAP1),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    asset_id = await _register_and_add_capability(deps)

    await remove_asset_capability.bind(deps)(
        RemoveAssetCapability(asset_id=asset_id, capability_id=_CAP1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Asset", asset_id)
    assert events[2].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_includes_remove_asset_capability() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.remove_asset_capability)
