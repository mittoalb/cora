"""Application handler for the `get_plan` query slice.

Cross-BC query-handler shape mirroring `get_practice` / `get_method`
/ `get_family` / `get_subject` / `get_actor`; extended to fold in
projection-sourced lifecycle timestamps per Path C (mirrors
Method):

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_plan(...)               -> Plan | None  (fold-on-read)
    3. load_plan_timestamps(...)    -> PlanLifecycleTimestamps | None
                                       (None when projection lags or
                                        pool not configured)
    4. return PlanView              -> caller maps None to 404 / isError;
                                       maps view.timestamps fields onto
                                       the response DTO

`PlanView` bundles the rich domain `Plan` with the projection-
sourced lifecycle metadata. State stays minimal per decider purity;
the timestamps live on the projection per Dudycz + K8s/GitHub/AIP-
142 resource-API precedent. Non-HTTP/MCP consumers that only need
the domain `Plan` should call `load_plan` directly — they sidestep
the projection read entirely.

Per gate-review Q4: get_plan returns CURRENT state only. The
audit snapshots in PlanDefined event payload (method_id,
method_needed_family_ids_snapshot, asset_families_snapshot)
are NOT exposed by this query — those are bind-time historical
data, accessible later via a separate audit query if pilot needs
it (deferred 6e-3+).

Query handlers do NOT emit `causation_id` log fields.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.plan import (
    Plan,
    PlanLifecycleTimestamps,
    load_plan,
    load_plan_timestamps,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.get_plan.query import GetPlan

_QUERY_NAME = "GetPlan"

_log = get_logger(__name__)


@dataclass(frozen=True)
class PlanView:
    """Read-side bundle: aggregate state + projection-sourced lifecycle
    timestamps. `timestamps` is None when the projection hasn't caught
    up yet OR when the deps lack a configured pool (in-memory test
    mode); both are transient/contextual, not a Plan-not-found
    signal (use a None `PlanView` for that)."""

    plan: Plan
    timestamps: PlanLifecycleTimestamps | None


class Handler(Protocol):
    """Callable interface every get_plan handler implements."""

    async def __call__(
        self,
        query: GetPlan,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> PlanView | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_plan handler closed over the shared deps."""

    async def handler(
        query: GetPlan,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> PlanView | None:
        _log.info(
            "get_plan.start",
            query_name=_QUERY_NAME,
            plan_id=str(query.plan_id),
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
                "get_plan.denied",
                query_name=_QUERY_NAME,
                plan_id=str(query.plan_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        plan = await load_plan(deps.event_store, query.plan_id)
        if plan is None:
            _log.info(
                "get_plan.success",
                query_name=_QUERY_NAME,
                plan_id=str(query.plan_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None

        timestamps: PlanLifecycleTimestamps | None = None
        if deps.pool is not None:
            timestamps = await load_plan_timestamps(deps.pool, query.plan_id)

        _log.info(
            "get_plan.success",
            query_name=_QUERY_NAME,
            plan_id=str(query.plan_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
            timestamps_present=timestamps is not None,
        )
        return PlanView(plan=plan, timestamps=timestamps)

    return handler
