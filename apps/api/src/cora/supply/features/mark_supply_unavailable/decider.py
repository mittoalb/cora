"""Pure decider for the `MarkSupplyUnavailable` command.

Multi-source transition (widest source set): `{Unknown, Available,
Degraded, Recovering} -> Unavailable`. Strict-not-idempotent: re-
marking an already-Unavailable supply raises.
"""

from datetime import datetime

from cora.supply.aggregates.supply import (
    Supply,
    SupplyCannotMarkUnavailableError,
    SupplyMarkedUnavailable,
    SupplyNotFoundError,
    SupplyReason,
    SupplyStatus,
    TriggerSource,
)
from cora.supply.features.mark_supply_unavailable.command import MarkSupplyUnavailable

_MARKABLE_UNAVAILABLE_STATUSES: frozenset[SupplyStatus] = frozenset(
    {
        SupplyStatus.UNKNOWN,
        SupplyStatus.AVAILABLE,
        SupplyStatus.DEGRADED,
        SupplyStatus.RECOVERING,
    }
)


def decide(
    state: Supply | None,
    command: MarkSupplyUnavailable,
    *,
    now: datetime,
) -> list[SupplyMarkedUnavailable]:
    """Decide the events produced by marking a Supply Unavailable."""
    if state is None:
        raise SupplyNotFoundError(command.supply_id)
    if state.status not in _MARKABLE_UNAVAILABLE_STATUSES:
        raise SupplyCannotMarkUnavailableError(state.id, state.status)

    reason = SupplyReason(command.reason)

    return [
        SupplyMarkedUnavailable(
            supply_id=state.id,
            from_status=state.status.value,
            reason=reason.value,
            trigger=TriggerSource.OPERATOR.value,
            occurred_at=now,
        )
    ]
