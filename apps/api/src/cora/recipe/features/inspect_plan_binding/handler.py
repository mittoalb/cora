"""Application handler for the `inspect_plan_binding` query slice.

Pre-loads the same upstream entities `define_plan` loads
(Practice -> Method -> Capability -> per-Asset -> per-Family),
then assembles an `InspectPlanBindingView` instead of emitting
events.

The load fan-out mirrors `define_plan.handler` exactly so the
preview diagnostic reflects what `define_plan` would actually
see at validation time. NotFound errors raised here use the same
exception classes `define_plan` raises and are HTTP-mapped by
`recipe/routes.py` to 404.

When `method.capability_id` is None (legacy Method shape), the
affordance guard is skipped; the view reports
`BindingStatus.MISSING_CAPABILITY` and leaves
`capability_required_affordances` + `missing_affordances` empty.
Matches `define_plan` decider's existing behaviour.

Query handlers do NOT emit `causation_id` log fields.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import Asset, AssetNotFoundError, load_asset
from cora.equipment.aggregates.family import (
    Affordance,
    FamilyNotFoundError,
    load_family,
)
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.capability import CapabilityNotFoundError, load_capability
from cora.recipe.aggregates.method import MethodNotFoundError, load_method
from cora.recipe.aggregates.practice import PracticeNotFoundError, load_practice
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.inspect_plan_binding.query import InspectPlanBinding
from cora.recipe.features.inspect_plan_binding.view import (
    BindingStatus,
    InspectPlanBindingView,
    WiredAssetBinding,
)

_QUERY_NAME = "InspectPlanBinding"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every inspect_plan_binding handler implements."""

    async def __call__(
        self,
        query: InspectPlanBinding,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> InspectPlanBindingView: ...


def bind(deps: Kernel) -> Handler:
    """Build an inspect_plan_binding handler closed over the shared deps."""

    async def handler(
        query: InspectPlanBinding,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> InspectPlanBindingView:
        _log.info(
            "inspect_plan_binding.start",
            query_name=_QUERY_NAME,
            practice_id=str(query.practice_id),
            asset_count=len(query.asset_ids),
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
                "inspect_plan_binding.denied",
                query_name=_QUERY_NAME,
                practice_id=str(query.practice_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        practice = await load_practice(deps.event_store, query.practice_id)
        if practice is None:
            raise PracticeNotFoundError(query.practice_id)

        method = await load_method(deps.event_store, practice.method_id)
        if method is None:
            raise MethodNotFoundError(practice.method_id)

        assets_in_order = sorted(query.asset_ids, key=str)
        assets: dict[UUID, Asset] = {}
        for asset_id in assets_in_order:
            asset = await load_asset(deps.event_store, asset_id)
            if asset is None:
                raise AssetNotFoundError(asset_id)
            assets[asset_id] = asset

        capability = None
        family_affordances: dict[UUID, frozenset[Affordance]] = {}
        union_families: frozenset[UUID] = frozenset(
            fid for asset in assets.values() for fid in asset.families
        )
        missing_families = method.needed_families - union_families

        if method.capability_id is not None:
            capability = await load_capability(deps.event_store, method.capability_id)
            if capability is None:
                raise CapabilityNotFoundError(method.capability_id)

            for family_id in sorted(union_families, key=str):
                family = await load_family(deps.event_store, family_id)
                if family is None:
                    raise FamilyNotFoundError(family_id)
                family_affordances[family_id] = family.affordances

        if capability is not None:
            union_affordances: frozenset[Affordance] = frozenset(
                affordance
                for asset in assets.values()
                for family_id in asset.families
                for affordance in family_affordances.get(family_id, frozenset())
            )
            missing_affordances = capability.required_affordances - union_affordances
            required_affordances = capability.required_affordances
        else:
            missing_affordances = frozenset[Affordance]()
            required_affordances = frozenset[Affordance]()

        if capability is None:
            binding_status = BindingStatus.MISSING_CAPABILITY
        elif missing_families:
            binding_status = BindingStatus.MISSING_FAMILIES
        elif missing_affordances:
            binding_status = BindingStatus.MISSING_AFFORDANCES
        else:
            binding_status = BindingStatus.SATISFIED

        wired_assets = tuple(
            WiredAssetBinding(
                asset_id=asset_id,
                asset_name=assets[asset_id].name.value,
                condition=assets[asset_id].condition,
                lifecycle=assets[asset_id].lifecycle,
                family_ids=assets[asset_id].families,
                contributed_affordances=frozenset(
                    affordance
                    for family_id in assets[asset_id].families
                    for affordance in family_affordances.get(family_id, frozenset())
                ),
            )
            for asset_id in assets_in_order
        )

        view = InspectPlanBindingView(
            practice_id=query.practice_id,
            method_id=method.id,
            capability_id=method.capability_id,
            method_needed_families=method.needed_families,
            capability_required_affordances=required_affordances,
            wired_assets=wired_assets,
            missing_families=missing_families,
            missing_affordances=missing_affordances,
            binding_status=binding_status,
        )

        _log.info(
            "inspect_plan_binding.success",
            query_name=_QUERY_NAME,
            practice_id=str(query.practice_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            binding_status=binding_status.value,
            asset_count=len(query.asset_ids),
            missing_family_count=len(missing_families),
            missing_affordance_count=len(missing_affordances),
        )
        return view

    return handler
