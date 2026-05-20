"""Application handler for the `get_calibration` query slice.

Cross-BC query-handler shape:

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_calibration(...)         -> Calibration | None  (fold-on-read)
    3. return state                  -> caller maps None to 404 / isError

Returns the domain `Calibration`, not a DTO. The route layer maps to
`CalibrationResponse` and the MCP tool maps to its own structured
output.
"""

from typing import Protocol
from uuid import UUID

from cora.calibration.aggregates.calibration import Calibration, load_calibration
from cora.calibration.errors import UnauthorizedError
from cora.calibration.features.get_calibration.query import GetCalibration
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "GetCalibration"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_calibration handler implements."""

    async def __call__(
        self,
        query: GetCalibration,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Calibration | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_calibration handler closed over the shared deps."""

    async def handler(
        query: GetCalibration,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Calibration | None:
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

        _log.info(
            "get_calibration.success",
            query_name=_QUERY_NAME,
            calibration_id=str(query.calibration_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=calibration is not None,
        )
        return calibration

    return handler
