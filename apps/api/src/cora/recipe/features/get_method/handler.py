"""Application handler for the `get_method` query slice.

Cross-BC query-handler shape (Phase 2b precedent, mirrored from
`get_family` / `get_asset` / `get_subject` / `get_actor`; extended
audit-2026-05-20 Iter A to fold in projection-sourced lifecycle
timestamps per Path C):

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_method(...)             -> Method | None  (fold-on-read)
    3. load_method_timestamps(...)  -> MethodLifecycleTimestamps | None
                                       (None when projection lags or
                                        pool not configured — same
                                        no-pool precedent as
                                        `make_list_query_handler`)
    4. return MethodView            -> caller maps None to 404 / isError;
                                       maps view.timestamps fields onto
                                       the response DTO

`MethodView` bundles the rich domain `Method` with the projection-
sourced lifecycle metadata. The state itself stays minimal per
decider purity (Chassaing/Pellegrini/Reynhout); the timestamps live
on the projection per Dudycz read-side-pragmatism + K8s/GitHub/
AIP-142 resource-API precedent. Non-HTTP/MCP consumers (other BCs,
sagas) that only need the domain `Method` should call `load_method`
directly — they sidestep the projection read entirely.

Query handlers do NOT emit `causation_id` log fields — queries have
no causation chain (they don't emit events that downstream commands
react to). Same convention as `get_family` / `get_asset`.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.method import (
    Method,
    MethodLifecycleTimestamps,
    load_method,
    load_method_timestamps,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.get_method.query import GetMethod

_QUERY_NAME = "GetMethod"

_log = get_logger(__name__)


@dataclass(frozen=True)
class MethodView:
    """Read-side bundle: aggregate state + projection-sourced lifecycle
    timestamps. `timestamps` is None when the projection hasn't caught
    up yet OR when the deps lack a configured pool (in-memory test
    mode); both are transient/contextual, not a Method-not-found
    signal (use a None `MethodView` for that)."""

    method: Method
    timestamps: MethodLifecycleTimestamps | None


class Handler(Protocol):
    """Callable interface every get_method handler implements."""

    async def __call__(
        self,
        query: GetMethod,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> MethodView | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_method handler closed over the shared deps."""

    async def handler(
        query: GetMethod,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> MethodView | None:
        _log.info(
            "get_method.start",
            query_name=_QUERY_NAME,
            method_id=str(query.method_id),
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
                "get_method.denied",
                query_name=_QUERY_NAME,
                method_id=str(query.method_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        method = await load_method(deps.event_store, query.method_id)
        if method is None:
            _log.info(
                "get_method.success",
                query_name=_QUERY_NAME,
                method_id=str(query.method_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None

        timestamps: MethodLifecycleTimestamps | None = None
        if deps.pool is not None:
            timestamps = await load_method_timestamps(deps.pool, query.method_id)

        _log.info(
            "get_method.success",
            query_name=_QUERY_NAME,
            method_id=str(query.method_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
            timestamps_present=timestamps is not None,
        )
        return MethodView(method=method, timestamps=timestamps)

    return handler
