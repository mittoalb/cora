"""Application handler for the `get_seal` query slice.

Cross-BC query-handler shape, extended to fold in projection-sourced
lifecycle timestamps per Path C (`project_template_aggregate_timestamps`):

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_seal(...)              -> Seal | None  (fold-on-read)
    3. load_seal_timestamps(...)   -> SealLifecycleTimestamps | None
                                      (None when projection lags or
                                       pool not configured)
    4. return SealView             -> caller maps None to 404 / isError;
                                      maps view.timestamps fields onto
                                      the response DTO

`SealView` bundles the domain `Seal` with the projection-sourced
lifecycle metadata. The aggregate state stays minimal per the Path C
convention; timestamps live on the projection. Non-HTTP/MCP consumers
that only need the domain `Seal` should call `load_seal` directly,
sidestepping the projection read entirely.

Singleton-per-facility: the query carries the human-readable
`facility_id` (str); the handler derives the deterministic stream
UUID via `seal_stream_id(facility_id)` before invoking `load_seal`.
`load_seal_timestamps` is keyed on the same `facility_id` directly
(the projection PK is `TEXT`).

Query handlers do NOT emit `causation_id` log fields, queries have
no causation chain.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.federation.aggregates.seal import (
    Seal,
    SealLifecycleTimestamps,
    load_seal,
    load_seal_timestamps,
)
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.federation.errors import UnauthorizedError
from cora.federation.features.get_seal.query import GetSeal
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "GetSeal"

_log = get_logger(__name__)


@dataclass(frozen=True)
class SealView:
    """Read-side bundle: aggregate state + projection-sourced lifecycle
    timestamps. `timestamps` is None when the projection hasn't caught
    up yet OR when the deps lack a configured pool (in-memory test
    mode); both are transient/contextual, not a Seal-not-found signal
    (use a None `SealView` for that)."""

    seal: Seal
    timestamps: SealLifecycleTimestamps | None


class Handler(Protocol):
    """Callable interface every get_seal handler implements."""

    async def __call__(
        self,
        query: GetSeal,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> SealView | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_seal handler closed over the shared deps."""

    async def handler(
        query: GetSeal,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> SealView | None:
        _log.info(
            "get_seal.start",
            query_name=_QUERY_NAME,
            facility_id=query.facility_id,
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
                "get_seal.denied",
                query_name=_QUERY_NAME,
                facility_id=query.facility_id,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stream_id = seal_stream_id(query.facility_id)
        seal = await load_seal(deps.event_store, stream_id)
        if seal is None:
            _log.info(
                "get_seal.success",
                query_name=_QUERY_NAME,
                facility_id=query.facility_id,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None

        timestamps: SealLifecycleTimestamps | None = None
        if deps.pool is not None:
            timestamps = await load_seal_timestamps(deps.pool, query.facility_id)

        _log.info(
            "get_seal.success",
            query_name=_QUERY_NAME,
            facility_id=query.facility_id,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
            timestamps_present=timestamps is not None,
        )
        return SealView(seal=seal, timestamps=timestamps)

    return handler
