"""Unit tests for the `version_capability` application handler.

Longhand handler (logs version_tag for diagnostic visibility). Tests
cover the multi-source guard, defensive version_tag validation, auth
deny, causation_id propagation, and wire smoke.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.capability import (
    CapabilityCannotVersionError,
    CapabilityNotFoundError,
    InvalidCapabilityVersionTagError,
)
from cora.equipment.features import (
    define_capability,
    deprecate_capability,
    version_capability,
)
from cora.equipment.features.define_capability import DefineCapability
from cora.equipment.features.deprecate_capability import DeprecateCapability
from cora.equipment.features.version_capability import VersionCapability
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
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000000ca01")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ca02")
_VERSIONED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ca03")
_DEPRECATED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ca04")
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
        id_generator=FixedIdGenerator(
            [
                _CAPABILITY_ID,
                _DEFINED_EVENT_ID,
                _VERSIONED_EVENT_ID,
                _DEPRECATED_EVENT_ID,
            ]
        ),
        authorize=DenyAllAuthorize() if deny else AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


async def _define_capability_helper(deps: SharedDeps) -> UUID:
    return await define_capability.bind(deps)(
        DefineCapability(name="Tomography"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    capability_id = await _define_capability_helper(deps)

    result = await version_capability.bind(deps)(
        VersionCapability(capability_id=capability_id, version_tag="v2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_capability_versioned_event_with_version_tag() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    capability_id = await _define_capability_helper(deps)

    await version_capability.bind(deps)(
        VersionCapability(capability_id=capability_id, version_tag="v2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Capability", capability_id)
    assert version == 2
    assert [e.event_type for e in events] == [
        "CapabilityDefined",
        "CapabilityVersioned",
    ]
    versioned = events[1]
    assert versioned.event_id == _VERSIONED_EVENT_ID
    assert versioned.metadata == {"command": "VersionCapability"}
    assert versioned.payload["version_tag"] == "v2"


@pytest.mark.unit
async def test_handler_supports_re_versioning() -> None:
    """Defined → Versioned → Versioned (subsequent revision)."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    capability_id = await _define_capability_helper(deps)
    handler = version_capability.bind(deps)

    await handler(
        VersionCapability(capability_id=capability_id, version_tag="v1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await handler(
        VersionCapability(capability_id=capability_id, version_tag="v2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Capability", capability_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "CapabilityDefined",
        "CapabilityVersioned",
        "CapabilityVersioned",
    ]
    assert events[1].payload["version_tag"] == "v1"
    assert events[2].payload["version_tag"] == "v2"


@pytest.mark.unit
async def test_handler_raises_capability_not_found_when_capability_does_not_exist() -> None:
    deps = _build_deps()
    handler = version_capability.bind(deps)

    with pytest.raises(CapabilityNotFoundError):
        await handler(
            VersionCapability(capability_id=_CAPABILITY_ID, version_tag="v1"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_version_tag_for_whitespace_only() -> None:
    """Defensive validation in the decider; pinned at handler layer."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    capability_id = await _define_capability_helper(deps)

    with pytest.raises(InvalidCapabilityVersionTagError):
        await version_capability.bind(deps)(
            VersionCapability(capability_id=capability_id, version_tag="   "),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_version_when_deprecated() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    capability_id = await _define_capability_helper(deps)

    await deprecate_capability.bind(deps)(
        DeprecateCapability(capability_id=capability_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    with pytest.raises(CapabilityCannotVersionError):
        await version_capability.bind(deps)(
            VersionCapability(capability_id=capability_id, version_tag="v2"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    capability_id = await _define_capability_helper(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError) as exc_info:
        await version_capability.bind(deny_deps)(
            VersionCapability(capability_id=capability_id, version_tag="v2"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    capability_id = await _define_capability_helper(deps)

    await version_capability.bind(deps)(
        VersionCapability(capability_id=capability_id, version_tag="v2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Capability", capability_id)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_includes_version_capability() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.version_capability)
