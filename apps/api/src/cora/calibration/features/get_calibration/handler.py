"""Application handler for the `get_calibration` query slice.

Cross-BC query-handler shape, extended to fold in projection-sourced
lifecycle timestamps per Path C (`project_template_aggregate_timestamps`):

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_calibration(...)              -> Calibration | None  (fold-on-read)
    3. load_calibration_timestamps(...)   -> CalibrationLifecycleTimestamps | None
                                             (None when projection lags or
                                              pool not configured)
    4. return CalibrationView             -> caller maps None to 404 / isError;
                                             maps view.timestamps fields onto
                                             the response DTO

`CalibrationView` bundles the rich domain `Calibration` with the
projection-sourced lifecycle metadata. The aggregate state stays
minimal per the Path C convention; timestamps live on the projection.
Non-HTTP/MCP consumers that only need the domain `Calibration` should
call `load_calibration` directly, sidestepping the projection read
entirely.

Query handlers do NOT emit `causation_id` log fields, queries have
no causation chain.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.calibration.aggregates.calibration import (
    Calibration,
    CalibrationLifecycleTimestamps,
    load_calibration,
    load_calibration_timestamps,
)
from cora.calibration.errors import UnauthorizedError
from cora.calibration.features.get_calibration.query import GetCalibration
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "GetCalibration"

_log = get_logger(__name__)


@dataclass(frozen=True)
class CalibrationView:
    """Read-side bundle: aggregate state + projection-sourced lifecycle
    timestamps. `timestamps` is None when the projection hasn't caught
    up yet OR when the deps lack a configured pool (in-memory test
    mode); both are transient/contextual, not a Calibration-not-found
    signal (use a None `CalibrationView` for that)."""

    calibration: Calibration
    timestamps: CalibrationLifecycleTimestamps | None


class Handler(Protocol):
    """Callable interface every get_calibration handler implements."""

    async def __call__(
        self,
        query: GetCalibration,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> CalibrationView | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_calibration handler closed over the shared deps."""

    async def handler(
        query: GetCalibration,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> CalibrationView | None:
        _log.info(
            "get_calibration.start",
            query_name=_QUERY_NAME,
            calibration_id=str(query.calibration_id),
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
                "get_calibration.denied",
                query_name=_QUERY_NAME,
                calibration_id=str(query.calibration_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        calibration = await load_calibration(deps.event_store, query.calibration_id)
        if calibration is None:
            _log.info(
                "get_calibration.success",
                query_name=_QUERY_NAME,
                calibration_id=str(query.calibration_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None

        timestamps: CalibrationLifecycleTimestamps | None = None
        if deps.pool is not None:
            timestamps = await load_calibration_timestamps(deps.pool, query.calibration_id)

        _log.info(
            "get_calibration.success",
            query_name=_QUERY_NAME,
            calibration_id=str(query.calibration_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
            timestamps_present=timestamps is not None,
        )
        return CalibrationView(calibration=calibration, timestamps=timestamps)

    return handler
