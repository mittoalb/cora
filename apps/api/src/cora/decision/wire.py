"""Compose the Decision BC's handlers from `SharedDeps`."""

from dataclasses import dataclass
from uuid import UUID

from cora.decision.features import get_decision, register_decision
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.observability import with_tracing

_BC = "decision"


@dataclass(frozen=True)
class DecisionHandlers:
    """The Decision BC's handler bundle, each closed over SharedDeps."""

    register_decision: register_decision.IdempotentHandler
    get_decision: get_decision.Handler


def wire_decision(deps: SharedDeps) -> DecisionHandlers:
    """Build the Decision BC handlers from shared dependencies."""
    return DecisionHandlers(
        register_decision=with_tracing(
            with_idempotency(
                register_decision.bind(deps),
                deps.idempotency_store,
                command_name="RegisterDecision",
                serialize_result=str,
                deserialize_result=UUID,
            ),
            command_name="RegisterDecision",
            bc=_BC,
        ),
        get_decision=with_tracing(
            get_decision.bind(deps),
            command_name="GetDecision",
            bc=_BC,
            kind="query",
        ),
    )
