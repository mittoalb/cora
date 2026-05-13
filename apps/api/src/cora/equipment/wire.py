"""Compose the Equipment BC's handlers from `Kernel`.

`wire_equipment(deps)` is invoked once from the FastAPI lifespan
and the returned `EquipmentHandlers` bundle is stored on
`app.state.equipment`. Routes and MCP tools pull their handler out
of that bundle. New slices (commands or queries) add a new field
on `EquipmentHandlers` and a single line in this factory.

Cross-cutting decorators applied here mirror Access / Trust /
Subject (composition order matters — innermost first):

1. `bind(deps)` — bare handler.
2. `with_idempotency` (create-style commands only) — Idempotency-Key
   support. Wrapped before tracing so cache-hits and cache-misses
   both attribute to the tracing span.
3. `with_tracing` — OTel span around every handler call. Records
   `cora.bc`, `cora.command` / `cora.query` attributes.

Phase 5a shipped `define_capability` + `get_capability`. Phase 5b
added `register_asset`. Phase 5c added `activate_asset` +
`decommission_asset`. Phase 5d adds `relocate_asset` (hierarchy
mutation; first event in the codebase whose payload carries source
AND target state). All transitions are update-style; not
idempotency-wrapped (domain-idempotent via `AssetCannot<X>Error`
on retry; same precedent as Subject's transitions). Queries skip
idempotency.

The per-aggregate `make_asset_update_handler` factory was extracted
in 5e (4 byte-identical Asset transitions; relocate stays longhand
because its log shape carries an extra to_parent_id field). Per-BC
naming was rejected because Equipment owns two aggregates: a
future Capability lifecycle factory will be a sibling
`make_capability_update_handler` rather than a parameterization of
this one.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.features import (
    activate_asset,
    add_asset_capability,
    decommission_asset,
    define_capability,
    deprecate_capability,
    enter_maintenance,
    get_asset,
    get_capability,
    list_assets,
    list_capabilities,
    register_asset,
    relocate_asset,
    remove_asset_capability,
    restore_from_maintenance,
    update_capability_schema,
    version_capability,
)
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing

_BC = "equipment"


@dataclass(frozen=True)
class EquipmentHandlers:
    """The Equipment BC's handler bundle, each closed over Kernel.

    Phase 5a shipped `define_capability` (create-style; idempotency-
    wrapped) and `get_capability` (read side). Phase 5b added
    `register_asset` (create-style; idempotency-wrapped). Phase 5c
    added the first two Asset lifecycle transitions: `activate_asset`
    and `decommission_asset`. Phase 5d adds `relocate_asset`
    (hierarchy mutation). All transition handlers are update-style
    with bare Handler protocols. The get_asset query (5e) and
    Capability transitions (5f+) land subsequently.
    """

    define_capability: define_capability.IdempotentHandler
    get_capability: get_capability.Handler
    version_capability: version_capability.Handler
    deprecate_capability: deprecate_capability.Handler
    update_capability_schema: update_capability_schema.Handler
    register_asset: register_asset.IdempotentHandler
    activate_asset: activate_asset.Handler
    decommission_asset: decommission_asset.Handler
    relocate_asset: relocate_asset.Handler
    enter_maintenance: enter_maintenance.Handler
    restore_from_maintenance: restore_from_maintenance.Handler
    add_asset_capability: add_asset_capability.Handler
    remove_asset_capability: remove_asset_capability.Handler
    get_asset: get_asset.Handler
    list_assets: list_assets.Handler
    list_capabilities: list_capabilities.Handler


def wire_equipment(deps: Kernel) -> EquipmentHandlers:
    """Build the Equipment BC handlers from shared dependencies."""
    return EquipmentHandlers(
        define_capability=with_tracing(
            with_idempotency(
                define_capability.bind(deps),
                deps.idempotency_store,
                command_name="DefineCapability",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefineCapability",
            bc=_BC,
        ),
        get_capability=with_tracing(
            get_capability.bind(deps),
            command_name="GetCapability",
            bc=_BC,
            kind="query",
        ),
        version_capability=with_tracing(
            version_capability.bind(deps),
            command_name="VersionCapability",
            bc=_BC,
        ),
        deprecate_capability=with_tracing(
            deprecate_capability.bind(deps),
            command_name="DeprecateCapability",
            bc=_BC,
        ),
        update_capability_schema=with_tracing(
            update_capability_schema.bind(deps),
            command_name="UpdateCapabilitySchema",
            bc=_BC,
        ),
        register_asset=with_tracing(
            with_idempotency(
                register_asset.bind(deps),
                deps.idempotency_store,
                command_name="RegisterAsset",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterAsset",
            bc=_BC,
        ),
        activate_asset=with_tracing(
            activate_asset.bind(deps),
            command_name="ActivateAsset",
            bc=_BC,
        ),
        decommission_asset=with_tracing(
            decommission_asset.bind(deps),
            command_name="DecommissionAsset",
            bc=_BC,
        ),
        relocate_asset=with_tracing(
            relocate_asset.bind(deps),
            command_name="RelocateAsset",
            bc=_BC,
        ),
        enter_maintenance=with_tracing(
            enter_maintenance.bind(deps),
            command_name="EnterMaintenance",
            bc=_BC,
        ),
        restore_from_maintenance=with_tracing(
            restore_from_maintenance.bind(deps),
            command_name="RestoreFromMaintenance",
            bc=_BC,
        ),
        add_asset_capability=with_tracing(
            add_asset_capability.bind(deps),
            command_name="AddAssetCapability",
            bc=_BC,
        ),
        remove_asset_capability=with_tracing(
            remove_asset_capability.bind(deps),
            command_name="RemoveAssetCapability",
            bc=_BC,
        ),
        get_asset=with_tracing(
            get_asset.bind(deps),
            command_name="GetAsset",
            bc=_BC,
            kind="query",
        ),
        list_assets=with_tracing(
            list_assets.bind(deps),
            command_name="ListAssets",
            bc=_BC,
            kind="query",
        ),
        list_capabilities=with_tracing(
            list_capabilities.bind(deps),
            command_name="ListCapabilities",
            bc=_BC,
            kind="query",
        ),
    )
