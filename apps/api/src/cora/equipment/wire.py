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

Phase 5a shipped `define_family` + `get_family`. Phase 5b
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
future Family lifecycle factory will be a sibling
`make_capability_update_handler` rather than a parameterization of
this one.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.features import (
    activate_asset,
    add_asset_family,
    add_asset_port,
    decommission_asset,
    define_family,
    degrade_asset,
    deprecate_family,
    enter_maintenance,
    fault_asset,
    get_asset,
    get_asset_integration_view,
    get_family,
    list_assets,
    list_families,
    register_asset,
    relocate_asset,
    remove_asset_family,
    remove_asset_port,
    restore_asset,
    restore_from_maintenance,
    update_asset_settings,
    update_family_settings_schema,
    version_family,
)
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing

_BC = "equipment"


@dataclass(frozen=True)
class EquipmentHandlers:
    """The Equipment BC's handler bundle, each closed over Kernel.

    Phase 5a shipped `define_family` (create-style; idempotency-
    wrapped) and `get_family` (read side). Phase 5b added
    `register_asset` (create-style; idempotency-wrapped). Phase 5c
    added the first two Asset lifecycle transitions: `activate_asset`
    and `decommission_asset`. Phase 5d adds `relocate_asset`
    (hierarchy mutation). All transition handlers are update-style
    with bare Handler protocols. The get_asset query (5e) and
    Family transitions (5f+) land subsequently.
    """

    define_family: define_family.IdempotentHandler
    get_family: get_family.Handler
    version_family: version_family.Handler
    deprecate_family: deprecate_family.Handler
    update_family_settings_schema: update_family_settings_schema.Handler
    register_asset: register_asset.IdempotentHandler
    activate_asset: activate_asset.Handler
    decommission_asset: decommission_asset.Handler
    relocate_asset: relocate_asset.Handler
    enter_maintenance: enter_maintenance.Handler
    restore_from_maintenance: restore_from_maintenance.Handler
    add_asset_family: add_asset_family.Handler
    remove_asset_family: remove_asset_family.Handler
    degrade_asset: degrade_asset.Handler
    fault_asset: fault_asset.Handler
    restore_asset: restore_asset.Handler
    update_asset_settings: update_asset_settings.Handler
    add_asset_port: add_asset_port.Handler
    remove_asset_port: remove_asset_port.Handler
    get_asset: get_asset.Handler
    get_asset_integration_view: get_asset_integration_view.Handler
    list_assets: list_assets.Handler
    list_families: list_families.Handler


def wire_equipment(deps: Kernel) -> EquipmentHandlers:
    """Build the Equipment BC handlers from shared dependencies."""
    return EquipmentHandlers(
        define_family=with_tracing(
            with_idempotency(
                define_family.bind(deps),
                deps.idempotency_store,
                command_name="DefineFamily",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefineFamily",
            bc=_BC,
        ),
        get_family=with_tracing(
            get_family.bind(deps),
            command_name="GetFamily",
            bc=_BC,
            kind="query",
        ),
        version_family=with_tracing(
            version_family.bind(deps),
            command_name="VersionFamily",
            bc=_BC,
        ),
        deprecate_family=with_tracing(
            deprecate_family.bind(deps),
            command_name="DeprecateFamily",
            bc=_BC,
        ),
        update_family_settings_schema=with_tracing(
            update_family_settings_schema.bind(deps),
            command_name="UpdateFamilySettingsSchema",
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
        add_asset_family=with_tracing(
            add_asset_family.bind(deps),
            command_name="AddAssetFamily",
            bc=_BC,
        ),
        remove_asset_family=with_tracing(
            remove_asset_family.bind(deps),
            command_name="RemoveAssetFamily",
            bc=_BC,
        ),
        degrade_asset=with_tracing(
            degrade_asset.bind(deps),
            command_name="DegradeAsset",
            bc=_BC,
        ),
        fault_asset=with_tracing(
            fault_asset.bind(deps),
            command_name="FaultAsset",
            bc=_BC,
        ),
        restore_asset=with_tracing(
            restore_asset.bind(deps),
            command_name="RestoreAsset",
            bc=_BC,
        ),
        update_asset_settings=with_tracing(
            update_asset_settings.bind(deps),
            command_name="UpdateAssetSettings",
            bc=_BC,
        ),
        add_asset_port=with_tracing(
            add_asset_port.bind(deps),
            command_name="AddAssetPort",
            bc=_BC,
        ),
        remove_asset_port=with_tracing(
            remove_asset_port.bind(deps),
            command_name="RemoveAssetPort",
            bc=_BC,
        ),
        get_asset=with_tracing(
            get_asset.bind(deps),
            command_name="GetAsset",
            bc=_BC,
            kind="query",
        ),
        get_asset_integration_view=with_tracing(
            get_asset_integration_view.bind(deps),
            command_name="GetAssetIntegrationView",
            bc=_BC,
            kind="query",
        ),
        list_assets=with_tracing(
            list_assets.bind(deps),
            command_name="ListAssets",
            bc=_BC,
            kind="query",
        ),
        list_families=with_tracing(
            list_families.bind(deps),
            command_name="ListFamilies",
            bc=_BC,
            kind="query",
        ),
    )
