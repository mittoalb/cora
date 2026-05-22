"""Application handler for the `get_capability` query slice.

Path C: handler returns CapabilityView
bundling aggregate state + projection-sourced lifecycle timestamps.
State stays minimal per decider purity; timestamps live on the
projection per Dudycz read-side-pragmatism + K8s/GitHub/AIP-142
resource-API precedent. Mirrors the pattern from Method, Plan,
Practice, and Family.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityLifecycleTimestamps,
    load_capability,
    load_capability_timestamps,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.get_capability.query import GetCapability

_QUERY_NAME = "GetCapability"

_log = get_logger(__name__)


@dataclass(frozen=True)
class CapabilityView:
    """Read-side bundle: aggregate state + projection-sourced lifecycle
    timestamps. `timestamps` is None when the projection hasn't caught
    up yet OR when the deps lack a configured pool (in-memory test
    mode)."""

    capability: Capability
    timestamps: CapabilityLifecycleTimestamps | None


class Handler(Protocol):
    """Callable interface every get_capability handler implements."""

    async def __call__(
        self,
        query: GetCapability,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> CapabilityView | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_capability handler closed over the shared deps."""

    async def handler(
        query: GetCapability,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> CapabilityView | None:
        _log.info(
            "get_capability.start",
            query_name=_QUERY_NAME,
            capability_id=str(query.capability_id),
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
                "get_capability.denied",
                query_name=_QUERY_NAME,
                capability_id=str(query.capability_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        capability = await load_capability(deps.event_store, query.capability_id)
        if capability is None:
            _log.info(
                "get_capability.success",
                query_name=_QUERY_NAME,
                capability_id=str(query.capability_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None

        timestamps: CapabilityLifecycleTimestamps | None = None
        if deps.pool is not None:
            timestamps = await load_capability_timestamps(deps.pool, query.capability_id)

        _log.info(
            "get_capability.success",
            query_name=_QUERY_NAME,
            capability_id=str(query.capability_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
            timestamps_present=timestamps is not None,
        )
        return CapabilityView(capability=capability, timestamps=timestamps)

    return handler
