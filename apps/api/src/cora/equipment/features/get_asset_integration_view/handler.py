# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

"""Application handler for the `get_asset_integration_view` query slice.

Read-time composition handler. Assembles the integration-view bundle by:

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_asset(...)                      -> Asset | None  (fold-on-read)
       (returns None → caller maps to 404 / isError)
    3. for each family in asset.families:
           load_family(...)                 -> Family | None (fold-on-read)
       (missing Family → skip with warning log; set incomplete=True; mirrors
        promote_dataset derived_from peer-load tolerance per
        [[project-dataset-lineage-design]])
    4. caution_lookup.find_active_for_run(
           asset_ids={asset_id}, procedure_ids=frozenset(),
           min_severity="Notice")           -> list[CautionReference]
       (port; existing infra; returns [] when pool is None / in test mode)
    5. SELECT FROM proj_recipe_capability_summary WHERE
           required_affordances <@ <combined Family affordances> AND
           status IN ('Defined', 'Versioned')
       (raw SQL via deps.pool; no-pool fallback returns [])
    6. assemble AssetIntegrationView and return

Returns the domain `AssetIntegrationView`, not a DTO. The route layer
maps to its own response model and the MCP tool maps to its own
structured output.

NO new event subscribers, NO new projection table, NO migration. v2
promotion to a denormalized projection (Option C from the Q1 memo)
is the explicit upgrade path; trigger documented in the design memo.

Per [[project-asset-integration-view-design]] anti-hook #5: missing-
Family-load tolerance returns `incomplete=True` rather than failing
loud. The known-active Cautions / applicable Capabilities pieces are
loaded from existing projections with the standard eventual-
consistency lag.
"""

from typing import Any, Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import Asset, load_asset
from cora.equipment.aggregates.family import Family, load_family
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.get_asset_integration_view.query import GetAssetIntegrationView
from cora.equipment.features.get_asset_integration_view.view import (
    AssetIntegrationView,
    CapabilityView,
    CautionView,
    FamilyView,
    PortView,
)
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "GetAssetIntegrationView"

_log = get_logger(__name__)


# v1 applicable-Capabilities SQL: filter by required_affordances containment +
# active status. The text[] `<@` operator returns rows whose
# required_affordances is a subset of the given array (i.e., this Asset's
# combined Family affordances cover the Capability's requirements).
# Status filter excludes Deprecated per the design lock.
_APPLICABLE_CAPABILITIES_SQL = """
SELECT capability_id, code, name, status
FROM proj_recipe_capability_summary
WHERE required_affordances <@ $1::text[]
  AND status IN ('Defined', 'Versioned')
ORDER BY code ASC
"""


class Handler(Protocol):
    """Callable interface every get_asset_integration_view handler implements."""

    async def __call__(
        self,
        query: GetAssetIntegrationView,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> AssetIntegrationView | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_asset_integration_view handler closed over the shared deps."""

    async def handler(
        query: GetAssetIntegrationView,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> AssetIntegrationView | None:
        _log.info(
            "get_asset_integration_view.start",
            query_name=_QUERY_NAME,
            asset_id=str(query.asset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "get_asset_integration_view.denied",
                query_name=_QUERY_NAME,
                asset_id=str(query.asset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Step 2: load Asset. None = stream empty -> caller maps to 404.
        asset = await load_asset(deps.event_store, query.asset_id)
        if asset is None:
            _log.info(
                "get_asset_integration_view.not_found",
                query_name=_QUERY_NAME,
                asset_id=str(query.asset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
            )
            return None

        # Step 3: load each referenced Family. Missing-Family tolerance:
        # skip with warning log and set incomplete=True on the response.
        # Mirrors [[project-dataset-lineage-design]] derived_from peer-load
        # tolerance pattern (operationally safe under the event-store
        # immutability guarantee; the warning surfaces if a Family stream
        # was admin-deleted out of band).
        loaded_families: list[Family] = []
        incomplete = False
        for family_id in sorted(asset.families, key=str):
            loaded = await load_family(deps.event_store, family_id)
            if loaded is None:
                _log.warning(
                    "get_asset_integration_view.family_missing",
                    query_name=_QUERY_NAME,
                    asset_id=str(query.asset_id),
                    family_id=str(family_id),
                    correlation_id=str(correlation_id),
                )
                incomplete = True
                continue
            loaded_families.append(loaded)

        # Combined affordances drive both the FamilyView output AND the
        # applicable-Capabilities filter. Affordance is a StrEnum; we
        # serialize each as its `.value` (matches what the Capability
        # projection stores as text[]).
        combined_affordance_values: set[str] = set()
        family_views: list[FamilyView] = []
        for family in loaded_families:
            family_affordance_values = frozenset(a.value for a in family.affordances)
            combined_affordance_values |= family_affordance_values
            family_views.append(
                FamilyView(
                    family_id=family.id,
                    name=family.name.value,
                    affordances=family_affordance_values,
                )
            )

        # Step 4: active Cautions on this Asset via the existing port.
        # `find_active_for_run` is named for its Run-start use case but
        # accepts arbitrary asset_ids; we pass a single-element set.
        # min_severity="Notice" widens to all 3 severities (Notice +
        # Caution + Warning) — the integration view consumer wants the
        # full advisory set, not the start-Run threshold filter.
        # In-memory test mode: the AlwaysQuietCautionLookup returns [].
        caution_refs = await deps.caution_lookup.find_active_for_run(
            asset_ids=frozenset({query.asset_id}),
            procedure_ids=frozenset(),
            min_severity="Notice",
        )
        caution_views = tuple(
            CautionView(
                caution_id=ref.caution_id,
                category=ref.category,
                severity=ref.severity,
                text=ref.text_excerpt,
            )
            for ref in caution_refs
        )

        # Step 5: applicable Capabilities via SQL (no-pool fallback for
        # in-memory test mode mirrors the list_query.no_pool convention
        # at [[project-list-query]] line 402; returns empty list).
        applicable_capability_views: tuple[CapabilityView, ...] = ()
        if deps.pool is None:
            _log.info(
                "get_asset_integration_view.no_pool",
                query_name=_QUERY_NAME,
                asset_id=str(query.asset_id),
                correlation_id=str(correlation_id),
            )
        else:
            async with deps.pool.acquire() as conn:
                rows: list[Any] = await conn.fetch(
                    _APPLICABLE_CAPABILITIES_SQL,
                    sorted(combined_affordance_values),
                )
            applicable_capability_views = tuple(
                CapabilityView(
                    capability_id=row["capability_id"],
                    code=row["code"],
                    name=row["name"],
                    status=row["status"],
                )
                for row in rows
            )

        # Step 6: assemble. Ports sorted by name for response determinism
        # (mirrors get_asset route convention).
        port_views = tuple(
            PortView(
                name=p.name,
                direction=p.direction.value,
                signal_type=p.signal_type,
            )
            for p in sorted(asset.ports, key=lambda port: port.name)
        )

        view = AssetIntegrationView(
            asset_id=asset.id,
            name=asset.name.value,
            level=asset.level.value,
            lifecycle=asset.lifecycle.value,
            condition=asset.condition.value,
            parent_id=asset.parent_id,
            families=tuple(family_views),
            ports=port_views,
            settings=asset.settings,
            active_cautions=caution_views,
            applicable_capabilities=applicable_capability_views,
            incomplete=incomplete,
        )

        _log.info(
            "get_asset_integration_view.success",
            query_name=_QUERY_NAME,
            asset_id=str(query.asset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            family_count=len(view.families),
            port_count=len(view.ports),
            caution_count=len(view.active_cautions),
            capability_count=len(view.applicable_capabilities),
            incomplete=view.incomplete,
        )
        return view

    return handler


_ = Asset  # re-export-friendly import; suppresses pyright reportUnusedImport
