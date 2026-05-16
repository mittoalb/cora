"""Application handler for the `get_plan` query slice.

Cross-BC query-handler shape mirroring `get_practice` / `get_method`
/ `get_capability` / `get_subject` / `get_actor`:

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_plan(...)               -> Plan | None  (fold-on-read)
    3. return state                 -> caller maps None to 404 / isError

Returns the domain `Plan`, not a DTO. The route + tool layers do
their own DTO mapping (primitives only).

Per gate-review Q4: get_plan returns CURRENT state only. The
audit snapshots in PlanDefined event payload (method_id,
method_needed_capabilities_snapshot, asset_capabilities_snapshot)
are NOT exposed by this query — those are bind-time historical
data, accessible later via a separate audit query if pilot needs
it (deferred 6e-3+).

Query handlers do NOT emit `causation_id` log fields.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.recipe.aggregates.plan import Plan, load_plan
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.get_plan.query import GetPlan

_QUERY_NAME = "GetPlan"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_plan handler implements."""

    async def __call__(
        self,
        query: GetPlan,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> Plan | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_plan handler closed over the shared deps."""

    async def handler(
        query: GetPlan,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> Plan | None:
        _log.info(
            "get_plan.start",
            query_name=_QUERY_NAME,
            plan_id=str(query.plan_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
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

        _log.info(
            "get_plan.success",
            query_name=_QUERY_NAME,
            plan_id=str(query.plan_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=plan is not None,
        )
        return plan

    return handler
