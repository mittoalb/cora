"""Application handler for the `get_practice` query slice.

Cross-BC query-handler shape mirroring `get_method` / `get_family`
/ `get_subject` / `get_actor`; extended audit-2026-05-20 Iter B-2
to fold in projection-sourced lifecycle timestamps per Path C
(mirrors Iter A on Method, Iter B-1 on Plan):

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_practice(...)             -> Practice | None  (fold-on-read)
    3. load_practice_timestamps(...)  -> PracticeLifecycleTimestamps | None
                                         (None when projection lags or
                                          pool not configured)
    4. return PracticeView            -> caller maps None to 404 / isError;
                                         maps view.timestamps fields onto
                                         the response DTO

`PracticeView` bundles the rich domain `Practice` with the
projection-sourced lifecycle metadata. State stays minimal per
decider purity; the timestamps live on the projection per Dudycz
read-side-pragmatism + K8s/GitHub/AIP-142 resource-API precedent.
Non-HTTP/MCP consumers that only need the domain `Practice` should
call `load_practice` directly — they sidestep the projection read
entirely.

Query handlers do NOT emit `causation_id` log fields.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.practice import (
    Practice,
    PracticeLifecycleTimestamps,
    load_practice,
    load_practice_timestamps,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.get_practice.query import GetPractice

_QUERY_NAME = "GetPractice"

_log = get_logger(__name__)


@dataclass(frozen=True)
class PracticeView:
    """Read-side bundle: aggregate state + projection-sourced lifecycle
    timestamps. `timestamps` is None when the projection hasn't caught
    up yet OR when the deps lack a configured pool (in-memory test
    mode); both are transient/contextual, not a Practice-not-found
    signal (use a None `PracticeView` for that)."""

    practice: Practice
    timestamps: PracticeLifecycleTimestamps | None


class Handler(Protocol):
    """Callable interface every get_practice handler implements."""

    async def __call__(
        self,
        query: GetPractice,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> PracticeView | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_practice handler closed over the shared deps."""

    async def handler(
        query: GetPractice,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> PracticeView | None:
        _log.info(
            "get_practice.start",
            query_name=_QUERY_NAME,
            practice_id=str(query.practice_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "get_practice.denied",
                query_name=_QUERY_NAME,
                practice_id=str(query.practice_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        practice = await load_practice(deps.event_store, query.practice_id)
        if practice is None:
            _log.info(
                "get_practice.success",
                query_name=_QUERY_NAME,
                practice_id=str(query.practice_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None

        timestamps: PracticeLifecycleTimestamps | None = None
        if deps.pool is not None:
            timestamps = await load_practice_timestamps(deps.pool, query.practice_id)

        _log.info(
            "get_practice.success",
            query_name=_QUERY_NAME,
            practice_id=str(query.practice_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
            timestamps_present=timestamps is not None,
        )
        return PracticeView(practice=practice, timestamps=timestamps)

    return handler
