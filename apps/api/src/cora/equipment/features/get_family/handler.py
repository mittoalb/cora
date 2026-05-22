"""Application handler for the `get_family` query slice.

Cross-BC query-handler shape, mirrored from
`get_actor` / `get_subject`; extended to fold in projection-sourced
lifecycle timestamps per Path C (mirrors Method, Plan, Practice):

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_family(...)             -> Family | None  (fold-on-read)
    3. load_family_timestamps(...)  -> FamilyLifecycleTimestamps | None
                                       (None when projection lags or
                                        pool not configured)
    4. return FamilyView            -> caller maps None to 404 / isError;
                                       maps view.timestamps fields onto
                                       the response DTO

`FamilyView` bundles the rich domain `Family` with the projection-
sourced lifecycle metadata. State stays minimal per decider purity;
the timestamps live on the projection per Dudycz read-side-
pragmatism + K8s/GitHub/AIP-142 resource-API precedent. Non-HTTP/MCP
consumers that only need the domain `Family` should call
`load_family` directly — they sidestep the projection read entirely.

Query handlers do NOT emit `causation_id` log fields — queries
have no causation chain (they don't emit events that downstream
commands react to). Same convention as `get_actor` / `get_subject`.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.family import (
    Family,
    FamilyLifecycleTimestamps,
    load_family,
    load_family_timestamps,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.get_family.query import GetFamily
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "GetFamily"

_log = get_logger(__name__)


@dataclass(frozen=True)
class FamilyView:
    """Read-side bundle: aggregate state + projection-sourced lifecycle
    timestamps. `timestamps` is None when the projection hasn't caught
    up yet OR when the deps lack a configured pool (in-memory test
    mode); both are transient/contextual, not a Family-not-found
    signal (use a None `FamilyView` for that)."""

    family: Family
    timestamps: FamilyLifecycleTimestamps | None


class Handler(Protocol):
    """Callable interface every get_family handler implements."""

    async def __call__(
        self,
        query: GetFamily,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> FamilyView | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_family handler closed over the shared deps."""

    async def handler(
        query: GetFamily,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> FamilyView | None:
        _log.info(
            "get_family.start",
            query_name=_QUERY_NAME,
            family_id=str(query.family_id),
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
                "get_family.denied",
                query_name=_QUERY_NAME,
                family_id=str(query.family_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        family = await load_family(deps.event_store, query.family_id)
        if family is None:
            _log.info(
                "get_family.success",
                query_name=_QUERY_NAME,
                family_id=str(query.family_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None

        timestamps: FamilyLifecycleTimestamps | None = None
        if deps.pool is not None:
            timestamps = await load_family_timestamps(deps.pool, query.family_id)

        _log.info(
            "get_family.success",
            query_name=_QUERY_NAME,
            family_id=str(query.family_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
            timestamps_present=timestamps is not None,
        )
        return FamilyView(family=family, timestamps=timestamps)

    return handler
